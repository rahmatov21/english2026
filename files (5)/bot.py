#!/usr/bin/env python3
"""
Halal Multi-Pair 1h Auto-Trader for MEXC Spot (Real-Time Edition).

Features:
- Real-Time Portfolio & Wallet Tracking: Continuously inspects and syncs actual crypto holdings.
- Real-Time Heartbeat: Logs live prices, token amounts, unrealized P&L, and next candle countdown every 15s.
- Order Book Slippage Protection: Inspects live bid/ask order book before every buy/sell to prevent late fills.
- Sizing Balance: 50%/50% 2-Tier DCA ensures balanced orders across pairs without over-spending.
- Signals: Confirmed LuxAlgo pivots (Length 7).
- Scale-Out: 2-Call Sell (50% first sell, remaining 50% rides on 2nd sell, no fixed take-profit cap).

Usage:
    python bot.py            # run the real-time auto-trader
    python bot.py backtest   # run multi-pair performance audit
    python bot.py chart      # start interactive web verification dashboard
"""
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import ccxt
from dotenv import load_dotenv

from luxalgo import find_signals

load_dotenv()

# ------------------------------- Configuration -----------------------------
MODE = os.getenv("MODE", "paper").lower()                      # paper | live
raw_symbols = os.getenv("SYMBOLS", os.getenv("SYMBOL", "GRAM/USDT,TAO/USDT"))
SYMBOLS = [s.strip() for s in raw_symbols.split(",") if s.strip()]

TIMEFRAME = os.getenv("TIMEFRAME", "1h")
PIVOT_LEN = int(os.getenv("PIVOT_LEN", "7"))                   # 7-hour confirmation delay
TIES = os.getenv("TIES", "left_strict")                       # equal-high handling ('left_strict' | 'both_equal')
BUY_TIER_PCT = float(os.getenv("BUY_TIER_PCT", "0.50"))       # 50% allocation per buy tier
MAX_BUY_TIERS = int(os.getenv("MAX_BUY_TIERS", "2"))           # Maximum 2 buy tiers (Tier 1, Tier 2)
SELL_CALL1_PCT = float(os.getenv("SELL_CALL1_PCT", "0.50"))     # 50% sold on 1st sell call
DIP_ONLY = os.getenv("DIP_ONLY", "true").lower() in ("true", "1", "yes")  # Tier 2 buy only if price is deeper
PAPER_START_USDT = float(os.getenv("PAPER_START_USDT", "100.0"))
FEE_RATE = float(os.getenv("FEE_RATE", "0.001"))               # 0.1% spot fee
MAX_SLIPPAGE_PCT = float(os.getenv("MAX_SLIPPAGE_PCT", "0.008")) # 0.8% maximum slippage protection collar
HEARTBEAT_SEC = int(os.getenv("HEARTBEAT_SEC", "15"))          # Real-time portfolio update frequency (seconds)
API_KEY = os.getenv("MEXC_API_KEY", "")
API_SECRET = os.getenv("MEXC_API_SECRET", "")
STATE_FILE = Path(os.getenv("STATE_FILE", f"state_{MODE}.json"))
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("bot.log", encoding="utf-8")],
)
log = logging.getLogger("halal-trader")

# Graceful server shutdown flag
RUNNING = True


def handle_shutdown(signum, frame):
    global RUNNING
    log.info("Received termination signal (%s). Finishing current cycle and stopping gracefully...", signum)
    RUNNING = False


signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


def make_exchange():
    ex = ccxt.mexc({
        "apiKey": API_KEY,
        "secret": API_SECRET,
        "enableRateLimit": True,
        "timeout": 20000,
        "options": {
            "adjustForTimeDifference": True,
            "recvWindow": 60000,
        },
    })
    ex.load_markets()
    for sym in SYMBOLS:
        if sym not in ex.markets:
            raise SystemExit(f"Symbol {sym} not found on MEXC Spot. Please verify SYMBOLS in .env")
    return ex


def get_closed_candles(ex, symbol, limit=500):
    tf_ms = ex.parse_timeframe(TIMEFRAME) * 1000
    raw = ex.fetch_ohlcv(symbol, TIMEFRAME, limit=limit)
    now = ex.milliseconds()
    return [c for c in raw if c[0] + tf_ms <= now]  # drop the still-forming candle


def get_order_book_quotes(ex, symbol):
    """Fetches real-time best bid and best ask to prevent bad fills or execution delay."""
    try:
        ob = ex.fetch_order_book(symbol, limit=5)
        best_bid = float(ob["bids"][0][0]) if ob.get("bids") else None
        best_ask = float(ob["asks"][0][0]) if ob.get("asks") else None
        spread_pct = ((best_ask - best_bid) / best_bid * 100) if (best_bid and best_ask) else 0.0
        return best_bid, best_ask, spread_pct
    except Exception as e:
        log.warning("[%s] Could not fetch real-time order book: %s", symbol, e)
        return None, None, 0.0


# ------------------------------- State Schema ------------------------------
def load_state():
    st = {
        "paper_usdt": PAPER_START_USDT,
        "total_pnl_usdt": 0.0,
        "pairs": {}
    }

    if STATE_FILE.exists():
        try:
            raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            st["paper_usdt"] = float(raw.get("paper_usdt", PAPER_START_USDT))
            st["total_pnl_usdt"] = float(raw.get("total_pnl_usdt", 0.0))

            if "pairs" in raw and isinstance(raw["pairs"], dict):
                st["pairs"] = raw["pairs"]
            else:
                legacy_sym = SYMBOLS[0] if SYMBOLS else "GRAM/USDT"
                st["pairs"][legacy_sym] = {
                    "last_ts": raw.get("last_ts"),
                    "buy_tier": raw.get("buy_tier", 0),
                    "sell_calls": raw.get("sell_calls", 0),
                    "tokens": raw.get("tokens", raw.get("amount", 0.0)),
                    "entry_lots": raw.get("entry_lots", []),
                }
        except Exception as e:
            log.warning("Could not parse %s (%s). Initializing fresh state.", STATE_FILE, e)

    # Ensure all configured symbols exist in state
    for sym in SYMBOLS:
        st["pairs"].setdefault(sym, {
            "last_ts": None,
            "buy_tier": 0,
            "sell_calls": 0,
            "tokens": 0.0,
            "entry_lots": []
        })

    return st


def save_state(st):
    """Atomic file write to prevent state corruption during server restart."""
    tmp_file = STATE_FILE.with_suffix(".tmp")
    tmp_file.write_text(json.dumps(st, indent=2), encoding="utf-8")
    os.replace(tmp_file, STATE_FILE)


# -------------------------- Real-Time Portfolio Sync -----------------------
def sync_wallet_portfolio(ex, st):
    """
    Synchronizes state directly with actual wallet balances on MEXC:
    - Queries free USDT and all held crypto tokens.
    - Calculates total net worth in real time.
    - Allows user full control: if tokens are deposited/withdrawn, the bot detects it.
    Returns: (total_net_worth_usdt, free_usdt, price_cache_dict)
    """
    px_cache = {}
    for sym in SYMBOLS:
        try:
            t = ex.fetch_ticker(sym)
            px_cache[sym] = float(t["last"])
        except Exception as e:
            log.warning("Could not fetch ticker for %s: %s", sym, e)
            px_cache[sym] = 0.0

    if MODE == "paper":
        free_usdt = float(st.get("paper_usdt", PAPER_START_USDT))
        held_val = 0.0
        for sym, p_state in st["pairs"].items():
            tok = float(p_state.get("tokens", 0.0))
            px = px_cache.get(sym, 0.0)
            held_val += tok * px
        net_worth = free_usdt + held_val
        return net_worth, free_usdt, px_cache

    # LIVE MODE: Direct query to exchange wallet
    bal = ex.fetch_balance()
    free_usdt = float(bal["free"].get("USDT", 0.0))
    total_usdt = float(bal["total"].get("USDT", 0.0))
    net_worth = total_usdt

    for sym in SYMBOLS:
        base_cur = sym.split("/")[0]
        wallet_free_tokens = float(bal["free"].get(base_cur, 0.0))
        wallet_total_tokens = float(bal["total"].get(base_cur, 0.0))
        cur_px = px_cache.get(sym, 0.0)

        # Sync actual wallet crypto with bot state
        p_state = st["pairs"][sym]
        if wallet_free_tokens > 0 and p_state["tokens"] == 0:
            p_state["tokens"] = wallet_free_tokens
            if not p_state["entry_lots"]:
                p_state["entry_lots"].append({
                    "tokens": wallet_free_tokens,
                    "price": cur_px,
                    "cost": wallet_free_tokens * cur_px,
                    "time": int(time.time()),
                    "tier": 1
                })
            log.info("[%s] Synced real wallet tokens: detected %.4f %s (~$%.2f)",
                     sym, wallet_free_tokens, base_cur, wallet_free_tokens * cur_px)

        token_val = wallet_total_tokens * cur_px
        if token_val > 0.5:
            net_worth += token_val

    return net_worth, free_usdt, px_cache


# ------------------------------- Execution ---------------------------------
def execute_buy(ex, st, symbol, signal_price, conf_bar_idx, piv_price):
    pos = st["pairs"][symbol]
    buy_tier = pos.get("buy_tier", 0)

    if buy_tier >= MAX_BUY_TIERS:
        log.info("[%s] BUY signal ignored: already reached maximum buy tiers (%d/%d)",
                 symbol, buy_tier, MAX_BUY_TIERS)
        return

    # Check deeper dip condition for Tier 2
    if buy_tier > 0 and DIP_ONLY and pos["entry_lots"]:
        last_entry_px = pos["entry_lots"][-1]["price"]
        if signal_price >= last_entry_px:
            log.info("[%s] BUY Tier %d skipped: current price %.5f is not deeper than previous entry %.5f",
                     symbol, buy_tier + 1, signal_price, last_entry_px)
            return

    # Fetch live order book to protect against slippage and execution delay
    best_bid, best_ask, spread_pct = get_order_book_quotes(ex, symbol)
    execution_price = best_ask or signal_price

    # Slippage Protection Collar: Don't buy if the live ask is more than MAX_SLIPPAGE_PCT above signal price
    slippage_pct = (execution_price - signal_price) / signal_price * 100
    if slippage_pct > (MAX_SLIPPAGE_PCT * 100):
        log.warning("[%s] BUY ABORTED: Price delay detected! Best Ask %.5f is %+.2f%% above signal price %.5f (max allowed: %.2f%%)",
                    symbol, execution_price, slippage_pct, signal_price, MAX_SLIPPAGE_PCT * 100)
        return

    net_worth, free_usdt, _ = sync_wallet_portfolio(ex, st)

    # 50% / 50% Sizing: 50% of available cash on Tier 1; remainder on Tier 2
    target_spend = min(net_worth * BUY_TIER_PCT, free_usdt)
    spend = min(target_spend, free_usdt)

    if spend < 5.0:
        log.warning("[%s] BUY skipped: insufficient free USDT ($%.2f free, minimum $5.00 required)",
                    symbol, free_usdt)
        return

    base_cur = symbol.split("/")[0]
    next_tier = buy_tier + 1
    log.info("[%s] Executing BUY Tier %d/%d: spending $%.2f at Best Ask %.5f (Spread: %.3f%%)",
             symbol, next_tier, MAX_BUY_TIERS, spend, execution_price, spread_pct)

    if MODE == "paper":
        fee = spend * FEE_RATE
        bought_tokens = (spend - fee) / execution_price
        st["paper_usdt"] -= spend
        filled_price = execution_price
    else:
        try:
            order = ex.create_market_buy_order_with_cost(symbol, spend)
        except (ccxt.NotSupported, AttributeError):
            amt = float(ex.amount_to_precision(symbol, spend / execution_price))
            order = ex.create_order(symbol, "market", "buy", amt, execution_price)
        try:
            order = ex.fetch_order(order["id"], symbol)
        except Exception:
            pass
        filled_tokens = order.get("filled") or (spend / execution_price * (1 - FEE_RATE))
        filled_price = order.get("average") or execution_price
        bought_tokens = filled_tokens

    pos["buy_tier"] = next_tier
    pos["sell_calls"] = 0
    pos["tokens"] += bought_tokens
    pos["entry_lots"].append({
        "tokens": bought_tokens,
        "price": filled_price,
        "cost": spend,
        "time": int(time.time()),
        "tier": next_tier
    })

    tot_tok = sum(l["tokens"] for l in pos["entry_lots"])
    tot_cost = sum(l["cost"] for l in pos["entry_lots"])
    avg_entry = tot_cost / tot_tok if tot_tok else filled_price

    log.info("[%s] BUY Tier %d SUCCESS: +%.4f %s @ %.5f | Total Tokens: %.4f | Avg Entry: %.5f",
             symbol, next_tier, bought_tokens, base_cur, filled_price, pos["tokens"], avg_entry)
    save_state(st)


def execute_sell(ex, st, symbol, signal_price, conf_bar_idx, piv_price):
    pos = st["pairs"][symbol]
    held_tokens = pos.get("tokens", 0.0)
    sell_calls = pos.get("sell_calls", 0)

    if held_tokens <= 0.0 or sell_calls >= 2:
        log.info("[%s] SELL signal ignored: no open position or already completed 2 scale-out calls", symbol)
        return

    # Fetch live order book to protect against slippage and execution delay
    best_bid, best_ask, spread_pct = get_order_book_quotes(ex, symbol)
    execution_price = best_bid or signal_price

    # Slippage Protection Collar: Don't sell if the live bid is more than MAX_SLIPPAGE_PCT below signal price
    drop_pct = (signal_price - execution_price) / signal_price * 100
    if drop_pct > (MAX_SLIPPAGE_PCT * 100):
        log.warning("[%s] SELL ABORTED: Price delay detected! Best Bid %.5f is %+.2f%% below signal price %.5f (max allowed: %.2f%%)",
                    symbol, execution_price, drop_pct, signal_price, MAX_SLIPPAGE_PCT * 100)
        return

    base_cur = symbol.split("/")[0]
    call_num = sell_calls + 1

    if call_num == 1:
        sell_amount = held_tokens * SELL_CALL1_PCT
        action_name = "SELL 1/2 (50% Scale-Out)"
    else:
        sell_amount = held_tokens  # all remaining tokens
        action_name = "SELL 2/2 (Final 100% Exit)"

    log.info("[%s] Executing %s: selling %.4f %s at Best Bid %.5f (Spread: %.3f%%)",
             symbol, action_name, sell_amount, base_cur, execution_price, spread_pct)

    if MODE == "paper":
        gross = sell_amount * execution_price
        fee = gross * FEE_RATE
        net_usdt = gross - fee
        st["paper_usdt"] += net_usdt
        filled_price = execution_price
    else:
        bal = ex.fetch_balance()
        free_base = float(bal["free"].get(base_cur, 0.0))
        amt_to_sell = float(ex.amount_to_precision(symbol, min(sell_amount, free_base)))
        if amt_to_sell <= 0:
            log.warning("[%s] LIVE: No %s available in wallet to sell", symbol, base_cur)
            return
        order = ex.create_market_sell_order(symbol, amt_to_sell)
        filled_price = order.get("average") or execution_price
        gross = amt_to_sell * filled_price
        fee = gross * FEE_RATE
        net_usdt = gross - fee

    # P&L accounting
    tot_tok = sum(l["tokens"] for l in pos["entry_lots"])
    tot_cost = sum(l["cost"] for l in pos["entry_lots"])
    avg_entry = tot_cost / tot_tok if tot_tok else filled_price
    cost_of_sold = tot_cost * (sell_amount / tot_tok) if tot_tok else net_usdt
    pnl_pct = (filled_price / avg_entry - 1) * 100
    pnl_usdt = net_usdt - cost_of_sold
    st["total_pnl_usdt"] = st.get("total_pnl_usdt", 0.0) + pnl_usdt

    log.info("[%s] %s SUCCESS: Sold %.4f %s @ %.5f | Trade P&L: %+.2f%% (%+$.2f USDT)",
             symbol, action_name, sell_amount, base_cur, filled_price, pnl_pct, pnl_usdt)

    pos["sell_calls"] = call_num
    pos["tokens"] -= sell_amount

    if call_num == 2 or pos["tokens"] < 1e-6:
        log.info("[%s] Position fully closed. Resetting tiers to 0. Realized P&L: %+$.2f USDT",
                 symbol, st["total_pnl_usdt"])
        pos["tokens"] = 0.0
        pos["buy_tier"] = 0
        pos["sell_calls"] = 0
        pos["entry_lots"] = []
    else:
        rem_ratio = pos["tokens"] / tot_tok
        pos["entry_lots"] = [{
            "tokens": pos["tokens"],
            "price": avg_entry,
            "cost": tot_cost * rem_ratio,
            "time": int(time.time()),
            "tier": pos["buy_tier"]
        }]
        pos["buy_tier"] = min(pos["buy_tier"], 1)

    save_state(st)


# -------------------------- Concurrent Processing --------------------------
def process_symbol(ex, st, symbol):
    """Processes signals for a single symbol on candle close."""
    pos = st["pairs"][symbol]
    candles = get_closed_candles(ex, symbol)
    if len(candles) < 2 * PIVOT_LEN + 2:
        log.warning("[%s] Not enough closed candles (%d)", symbol, len(candles))
        return

    ts = [c[0] for c in candles]
    highs = [c[2] for c in candles]
    lows = [c[3] for c in candles]
    signals = find_signals(highs, lows, PIVOT_LEN, TIES)

    if pos["last_ts"] is None:
        if signals:
            last_conf_idx, last_side, last_piv_idx, last_piv_price = signals[-1]
            pos["last_ts"] = ts[last_conf_idx]
            log.info("[%s] State initialized. Latest confirmed signal: %s @ %.5f (bar %d)",
                     symbol, last_side.upper(), last_piv_price, last_conf_idx)
            if last_side == "buy" and pos["buy_tier"] == 0:
                cur_px = candles[-1][4]
                log.info("[%s] Active indicator BUY signal detected. Syncing initial position...", symbol)
                execute_buy(ex, st, symbol, cur_px, last_conf_idx, last_piv_price)
            elif last_side == "sell":
                log.info("[%s] Indicator is in SELL/cash state. Waiting for next BUY signal.", symbol)
        else:
            pos["last_ts"] = ts[-1]
            log.info("[%s] State initialized. Waiting for next hourly candle close.", symbol)
        return

    cur_price = candles[-1][4]
    for conf_idx, side, piv_idx, piv_price in signals:
        if ts[conf_idx] <= pos["last_ts"]:
            continue
        log.info("[%s] NEW SIGNAL CONFIRMED: %s @ %.5f (formed %d hours ago)",
                 symbol, side.upper(), piv_price, conf_idx - piv_idx)
        if side == "buy":
            execute_buy(ex, st, symbol, cur_price, conf_idx, piv_price)
        else:
            execute_sell(ex, st, symbol, cur_price, conf_idx, piv_price)

    pos["last_ts"] = ts[-1]


def process_all_pairs(ex, st):
    """Processes all configured pairs simultaneously in each hourly round."""
    for symbol in SYMBOLS:
        try:
            process_symbol(ex, st, symbol)
        except Exception as e:
            log.error("[%s] Error in processing cycle: %s", symbol, e)
    save_state(st)


# -------------------------- Real-Time Heartbeat Loop -----------------------
def run():
    global RUNNING
    ex = make_exchange()
    if MODE == "live" and not (API_KEY and API_SECRET):
        raise SystemExit("MODE=live requires MEXC_API_KEY and MEXC_API_SECRET in your .env file")

    st = load_state()
    net_worth, free_usdt, px_cache = sync_wallet_portfolio(ex, st)

    log.info("=" * 75)
    log.info("  STARTING REAL-TIME HALAL MULTI-PAIR AUTO-TRADER (MEXC SPOT)")
    log.info("  Active Pairs: %s", ", ".join(SYMBOLS))
    log.info("  Timeframe: %s | Pivot Length: %d | Slippage Protection: %.2f%%",
             TIMEFRAME, PIVOT_LEN, MAX_SLIPPAGE_PCT * 100)
    log.info("  Strategy: 2-Tier DCA (50%% / 50%% Spot Buy) + 2-Call Sell (50%% / 50%%)")
    log.info("  Mode: %s | Account Net Worth: $%.2f USDT (Free: $%.2f)", MODE.upper(), net_worth, free_usdt)
    for sym in SYMBOLS:
        p_state = st["pairs"][sym]
        log.info("    -> %s: Tier %d/%d | Sells: %d/2 | Held: %.4f tokens ($%.2f)",
                 sym, p_state["buy_tier"], MAX_BUY_TIERS, p_state["sell_calls"],
                 p_state["tokens"], p_state["tokens"] * px_cache.get(sym, 0.0))
    log.info("=" * 75)

    tf_s = ex.parse_timeframe(TIMEFRAME)

    while RUNNING:
        # 1. Hourly candle close processing
        try:
            log.info("Running hourly candle check across %d symbols...", len(SYMBOLS))
            process_all_pairs(ex, st)
            save_state(st)
        except Exception as e:
            log.error("Unexpected error in candle processing loop: %s. Retrying in 15s...", e)
            time.sleep(15)
            continue

        if not RUNNING:
            break

        # 2. Real-Time Heartbeat & Portfolio Monitor until next candle close
        now = time.time()
        wait = tf_s - (now % tf_s) + 5
        wake_target = time.time() + wait
        log.info("Hourly check complete. Entering real-time monitoring mode (Next candle in %dm %ds)...",
                 int(wait // 60), int(wait % 60))

        last_heartbeat = 0
        while RUNNING and time.time() < wake_target:
            cur_t = time.time()
            if cur_t - last_heartbeat >= HEARTBEAT_SEC:
                last_heartbeat = cur_t
                try:
                    # Sync real-time portfolio & market prices
                    nw, free_cash, px_now = sync_wallet_portfolio(ex, st)
                    save_state(st)

                    status_parts = []
                    for sym in SYMBOLS:
                        base = sym.split("/")[0]
                        p_state = st["pairs"][sym]
                        held = p_state.get("tokens", 0.0)
                        px = px_now.get(sym, 0.0)
                        if held > 0:
                            tot_tok = sum(l["tokens"] for l in p_state["entry_lots"])
                            tot_cost = sum(l["cost"] for l in p_state["entry_lots"])
                            avg_entry = tot_cost / tot_tok if tot_tok else px
                            pnl_pct = (px / avg_entry - 1) * 100 if avg_entry else 0.0
                            status_parts.append(f"{base}: {held:.2f} tok (${held*px:.2f}, {pnl_pct:+.2f}%) @ {px:.4f}")
                        else:
                            status_parts.append(f"{base}: ${px:.4f} (Cash)")

                    rem_sec = max(0, int(wake_target - cur_t))
                    rem_str = f"{rem_sec // 60}m {rem_sec % 60:02d}s"

                    log.info("[REAL-TIME] NW: $%.2f (Free: $%.2f) | %s | Next Bar: %s",
                             nw, free_cash, " | ".join(status_parts), rem_str)
                except Exception as err:
                    log.debug("Heartbeat error: %s", err)

            time.sleep(1.0)

    log.info("Halal Auto-Trader has exited cleanly. State saved.")


# ------------------------------- Backtest ----------------------------------
def backtest():
    import chart
    ex = make_exchange()
    print("=" * 80)
    print("  MULTI-PAIR HALAL STRATEGY AUDIT (1H SPOT, 50%/50% DCA)")
    print(f"  Pairs: {', '.join(SYMBOLS)}")
    print("=" * 80)

    for sym in SYMBOLS:
        candles = chart.fetch_history(ex, sym, "1h", 2000)
        tf_ms = ex.parse_timeframe("1h") * 1000
        now = ex.milliseconds()
        closed = [c for c in candles if c[0] + tf_ms <= now]
        start_dt = datetime.fromtimestamp(closed[0][0] / 1000, timezone.utc)
        end_dt = datetime.fromtimestamp(closed[-1][0] / 1000, timezone.utc)
        duration_days = (end_dt - start_dt).total_seconds() / 86400

        print(f"\n>>> {sym} ({len(closed)} candles | {start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')} | {duration_days:.1f} days) <<<")
        print(f"{'Length':<8} | {'Final ($50)':<12} | {'Net Profit':<12} | {'Buy & Hold':<12} | {'Sells':<6} | {'Win Rate':<10} | {'Max DD':<10} | {'Fees':<8}")
        print("-" * 88)

        for l in [6, 7, 8, 10]:
            _, rts, sm = chart.simulate_bot_trades(closed, length=l, initial_balance=50.0, mode="dca2", require_deeper=True)
            print(f"Len {l:<4} | ${sm['final_balance']:<10.2f} | {sm['pct_profit']:>+6.2f}%     | {sm['bh_ret']:>+6.2f}%     | {sm['total_roundtrips']:<6} | {sm['win_rate']:>5.1f}%    | {sm['max_dd']:>5.2f}%   | ${sm['total_fees']:<6.2f}")
    print("=" * 80)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "backtest":
        backtest()
    elif cmd == "chart":
        import chart
        chart.run()
    else:
        run()
