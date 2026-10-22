#!/usr/bin/env python3
"""
Interactive chart & trade verification page:
Candles + exact times and prices where the bot BOUGHT and SOLD every trade.
Supports 3-Tier DCA (33%) + 2-Call Scale-Out (50%) and Single-entry modes.
Open http://localhost:8000 after starting:
    python chart.py
"""
import json
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import ccxt

from luxalgo import luxalgo, find_signals

HERE = Path(__file__).parent
PORT = int(os.getenv("CHART_PORT", "8000"))
PAGE_SIZE = {"okx": 100, "mexc": 500, "binance": 1000, "bybit": 1000}
_exchanges = {}


def get_ex(name):
    if name not in _exchanges:
        _exchanges[name] = getattr(ccxt, name)({"enableRateLimit": True})
        _exchanges[name].load_markets()
    return _exchanges[name]


def fetch_history(ex, symbol, tf, limit):
    tf_ms = ex.parse_timeframe(tf) * 1000
    page = PAGE_SIZE.get(ex.id, 200)
    since = ex.milliseconds() - limit * tf_ms
    out, seen = [], set()
    for _ in range(60):
        batch = ex.fetch_ohlcv(symbol, tf, since=since, limit=page)
        new = [c for c in batch if c[0] not in seen]
        if not new:
            break
        for c in new:
            seen.add(c[0])
            out.append(c)
        since = max(c[0] for c in new) + tf_ms
        if since >= ex.milliseconds():
            break
    out.sort()
    return out[-limit:]


def simulate_bot_trades(candles, length=7, initial_balance=50.0, mode="dca3", require_deeper=True, buy_pct=0.5, sell_pct=1.0, fee_rate=0.001):
    """
    True walk-forward testing of the bot strategy:
    - mode="dca3": 3-Tier Scale-In (33% networth each buy) + 2-Call Scale-Out (50% first sell, remaining 50% second sell).
    - mode="single": Single position entry (buy_pct of available cash), single exit (sell_pct).
    """
    if len(candles) < 2 * length + 2:
        return [], [], {}

    highs = [c[2] for c in candles]
    lows = [c[3] for c in candles]
    closes = [c[4] for c in candles]

    sigs = find_signals(highs, lows, length, "left_strict")

    usdt = initial_balance
    tokens = 0.0
    buy_tier = 0
    sell_calls = 0
    entry_lots = []
    trades_log = []
    round_trips = []
    gross_profit = 0.0
    gross_loss = 0.0
    peak_portfolio = initial_balance
    max_dd = 0.0
    total_fees = 0.0

    start_ts = candles[0][0]
    end_ts = candles[-1][0]
    start_dt = datetime.fromtimestamp(start_ts / 1000, timezone.utc)
    end_dt = datetime.fromtimestamp(end_ts / 1000, timezone.utc)
    duration_days = (end_dt - start_dt).total_seconds() / 86400

    for conf_idx, side, piv_idx, piv_price in sigs:
        if conf_idx + 1 >= len(candles):
            continue
        nxt = candles[conf_idx + 1]
        fill_price = nxt[1]
        fill_ts = nxt[0] // 1000

        # Update high-water mark and drawdown
        port_val = usdt + tokens * fill_price
        if port_val > peak_portfolio:
            peak_portfolio = port_val
        dd = (peak_portfolio - port_val) / peak_portfolio * 100
        if dd > max_dd:
            max_dd = dd

        # --- BUY SIGNAL ---
        if side == "buy":
            if mode in ("dca2", "dca3"):
                num_tiers = 2 if mode == "dca2" else 3
                can_buy = False
                if buy_tier == 0:
                    can_buy = True
                elif buy_tier < num_tiers:
                    if require_deeper and entry_lots:
                        last_entry = entry_lots[-1][1]
                        if fill_price < last_entry:
                            can_buy = True
                    else:
                        can_buy = True

                if can_buy and usdt >= 1.0:
                    buy_tier += 1
                    target_spend = port_val / float(num_tiers)
                    spend = min(target_spend, usdt)
                    if buy_tier == num_tiers:
                        spend = usdt

                    fee = spend * fee_rate
                    total_fees += fee
                    bought_tokens = (spend - fee) / fill_price
                    usdt -= spend
                    tokens += bought_tokens
                    entry_lots.append((bought_tokens, fill_price, spend))
                    sell_calls = 0

                    tot_tok = sum(t for t, p, c in entry_lots)
                    avg_entry = sum(t * p for t, p, c in entry_lots) / tot_tok

                    tier_pct_str = "50%" if mode == "dca2" else "33%"
                    trades_log.append({
                        "time": fill_ts,
                        "action": f"BUY T{buy_tier} ({tier_pct_str})",
                        "side": "buy",
                        "price": fill_price,
                        "tokens": bought_tokens,
                        "flow": -spend,
                        "avg_entry": avg_entry,
                        "pnl": "-",
                        "pnl_num": 0.0,
                        "cash": usdt,
                        "tokens_held": tokens,
                        "port_val": usdt + tokens * fill_price,
                        "piv_price": piv_price,
                        "conf_bar": conf_idx
                    })

            else:  # mode == "single"
                if tokens == 0.0:
                    spend = usdt * buy_pct
                    if spend >= 1.0:
                        fee = spend * fee_rate
                        total_fees += fee
                        bought_tokens = (spend - fee) / fill_price
                        usdt -= spend
                        tokens = bought_tokens
                        entry_lots = [(bought_tokens, fill_price, spend)]

                        trades_log.append({
                            "time": fill_ts,
                            "action": f"BUY ({int(buy_pct * 100)}% Bal)",
                            "side": "buy",
                            "price": fill_price,
                            "tokens": bought_tokens,
                            "flow": -spend,
                            "avg_entry": fill_price,
                            "pnl": "-",
                            "pnl_num": 0.0,
                            "cash": usdt,
                            "tokens_held": tokens,
                            "port_val": usdt + tokens * fill_price,
                            "piv_price": piv_price,
                            "conf_bar": conf_idx
                        })

        # --- SELL SIGNAL ---
        elif side == "sell":
            if mode in ("dca2", "dca3"):
                if tokens > 0.0 and sell_calls < 2:
                    sell_calls += 1
                    if sell_calls == 1:
                        sell_tokens = tokens * 0.5
                        action_label = "SELL 1/2 (50%)"
                    else:
                        sell_tokens = tokens
                        action_label = "SELL 2/2 (Final 50%)"

                    gross = sell_tokens * fill_price
                    fee = gross * fee_rate
                    total_fees += fee
                    net = gross - fee
                    usdt += net

                    tot_tok = sum(t for t, p, c in entry_lots)
                    avg_entry = sum(t * p for t, p, c in entry_lots) / tot_tok if tot_tok else fill_price
                    tot_cost = sum(c for t, p, c in entry_lots)
                    cost_of_sold = tot_cost * (sell_tokens / tot_tok) if tot_tok else net

                    trade_pnl_pct = (fill_price / avg_entry - 1) * 100
                    trade_pnl_usdt = net - cost_of_sold

                    if trade_pnl_usdt > 0:
                        gross_profit += trade_pnl_usdt
                    else:
                        gross_loss += abs(trade_pnl_usdt)

                    round_trips.append({
                        "exit_time": fill_ts,
                        "action": action_label,
                        "entry_price": avg_entry,
                        "exit_price": fill_price,
                        "pnl_pct": trade_pnl_pct,
                        "pnl_usdt": trade_pnl_usdt,
                        "win": trade_pnl_pct > 0
                    })

                    tokens -= sell_tokens
                    if tokens < 1e-6 or sell_calls == 2:
                        tokens = 0.0
                        buy_tier = 0
                        sell_calls = 0
                        entry_lots = []
                    else:
                        rem_ratio = tokens / tot_tok
                        entry_lots = [(tokens, avg_entry, tot_cost * rem_ratio)]
                        buy_tier = min(buy_tier, 2)

                    trades_log.append({
                        "time": fill_ts,
                        "action": action_label,
                        "side": "sell",
                        "price": fill_price,
                        "tokens": sell_tokens,
                        "flow": net,
                        "avg_entry": avg_entry,
                        "pnl": f"{trade_pnl_pct:+.2f}% (${trade_pnl_usdt:+.2f})",
                        "pnl_num": trade_pnl_pct,
                        "pnl_usdt": trade_pnl_usdt,
                        "cash": usdt,
                        "tokens_held": tokens,
                        "port_val": usdt + tokens * fill_price,
                        "piv_price": piv_price,
                        "conf_bar": conf_idx
                    })

            else:  # mode == "single"
                if tokens > 0.0:
                    sold_tokens = tokens * sell_pct
                    gross = sold_tokens * fill_price
                    fee = gross * fee_rate
                    total_fees += fee
                    net = gross - fee
                    usdt += net

                    entry_price = entry_lots[0][1]
                    entry_cost = entry_lots[0][2]
                    trade_pnl_pct = (fill_price / entry_price - 1) * 100
                    trade_pnl_usdt = net - entry_cost

                    if trade_pnl_usdt > 0:
                        gross_profit += trade_pnl_usdt
                    else:
                        gross_loss += abs(trade_pnl_usdt)

                    round_trips.append({
                        "exit_time": fill_ts,
                        "action": f"SELL ({int(sell_pct * 100)}%)",
                        "entry_price": entry_price,
                        "exit_price": fill_price,
                        "pnl_pct": trade_pnl_pct,
                        "pnl_usdt": trade_pnl_usdt,
                        "win": trade_pnl_pct > 0
                    })

                    tokens -= sold_tokens
                    if tokens < 1e-6:
                        tokens = 0.0
                        entry_lots = []

                    trades_log.append({
                        "time": fill_ts,
                        "action": f"SELL ({int(sell_pct * 100)}%)",
                        "side": "sell",
                        "price": fill_price,
                        "tokens": sold_tokens,
                        "flow": net,
                        "avg_entry": entry_price,
                        "pnl": f"{trade_pnl_pct:+.2f}% (${trade_pnl_usdt:+.2f})",
                        "pnl_num": trade_pnl_pct,
                        "pnl_usdt": trade_pnl_usdt,
                        "cash": usdt,
                        "tokens_held": tokens,
                        "port_val": usdt + tokens * fill_price,
                        "piv_price": piv_price,
                        "conf_bar": conf_idx
                    })

    last_price = closes[-1]
    final_token_val = tokens * last_price
    final_balance = usdt + final_token_val
    net_profit = final_balance - initial_balance
    pct_profit = (net_profit / initial_balance) * 100

    bh_entry = candles[min(length, len(candles) - 1)][1]
    bh_ret = (last_price / bh_entry - 1) * 100
    bh_final = initial_balance * (1 + bh_ret / 100)

    wins = [rt for rt in round_trips if rt["win"]]
    losses = [rt for rt in round_trips if not rt["win"]]
    win_rate = (len(wins) / len(round_trips) * 100) if round_trips else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 999.0
    avg_win = sum(rt["pnl_pct"] for rt in wins) / len(wins) if wins else 0.0
    avg_loss = sum(rt["pnl_pct"] for rt in losses) / len(losses) if losses else 0.0

    summary = {
        "initial_balance": initial_balance,
        "final_balance": final_balance,
        "cash_balance": usdt,
        "token_val": final_token_val,
        "tokens_held": tokens,
        "net_profit": net_profit,
        "pct_profit": pct_profit,
        "bh_final": bh_final,
        "bh_ret": bh_ret,
        "duration_days": duration_days,
        "duration_months": duration_days / 30.4375,
        "duration_hours": duration_days * 24,
        "start_date": start_dt.strftime("%Y-%m-%d %H:%M UTC"),
        "end_date": end_dt.strftime("%Y-%m-%d %H:%M UTC"),
        "candles_count": len(candles),
        "total_ops": len(trades_log),
        "total_roundtrips": len(round_trips),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "max_dd": max_dd,
        "total_fees": total_fees,
        "mode": mode,
        "require_deeper": require_deeper
    }
    return trades_log, round_trips, summary


def build_payload(q):
    name = q.get("exchange", ["mexc"])[0]
    symbol = q.get("symbol", ["GRAM/USDT"])[0]
    tf = q.get("tf", ["1h"])[0]
    limit = min(int(q.get("limit", ["4000"])[0]), 6000)
    length = int(q.get("length", ["8"])[0])
    ties = q.get("ties", ["left_strict"])[0]
    start_bal = float(q.get("balance", ["50"])[0])
    mode = q.get("mode", ["dca3"])[0]
    require_deeper = q.get("deeper", ["1"])[0] in ["1", "true", "True"]
    buy_pct = float(q.get("buy_pct", ["50"])[0]) / 100.0
    sell_pct = float(q.get("sell_pct", ["100"])[0]) / 100.0

    ex = get_ex(name)
    candles = fetch_history(ex, symbol, tf, limit)
    tf_ms = ex.parse_timeframe(tf) * 1000
    now = ex.milliseconds()
    closed = [c for c in candles if c[0] + tf_ms <= now]
    res = luxalgo([c[2] for c in closed], [c[3] for c in closed], length, ties)
    t = lambda i: closed[i][0] // 1000

    regular = [{"time": t(p), "confirm_time": t(c), "side": s, "price": px}
               for c, s, p, px in res["regular"]]
    ghosts = [{"time": t(i), "kind": k, "price": px} for i, k, px in res["ghosts"]]
    segs = [{"t1": t(a), "p1": b, "t2": t(c), "p2": d, "dashed": e} for a, b, c, d, e in res["segs"]]
    prov = None
    if res["provisional"]:
        p = res["provisional"]
        prov = {"time": t(p["x"]), "price": p["y"], "kind": p["kind"],
                "from_time": t(p["from"][0]), "from_price": p["from"][1]}

    # Run true bot simulation
    bot_trades, round_trips, summary = simulate_bot_trades(
        closed, length=length, initial_balance=start_bal, mode=mode,
        require_deeper=require_deeper, buy_pct=buy_pct, sell_pct=sell_pct
    )

    return {
        "exchange": name, "symbol": symbol, "tf": tf,
        "candles": [{"time": c[0] // 1000, "open": c[1], "high": c[2], "low": c[3], "close": c[4]}
                    for c in candles],
        "regular": regular, "ghosts": ghosts, "segs": segs, "provisional": prov,
        "bot_trades": bot_trades, "round_trips": round_trips, "summary": summary,
        "closed_until": t(len(closed) - 1) if closed else None,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError):
            pass

    def do_GET(self):
        u = urlparse(self.path)
        try:
            if u.path == "/":
                self._send(200, PAGE.encode(), "text/html; charset=utf-8")
            elif u.path == "/lw.js":
                self._send(200, (HERE / "lw.js").read_bytes(), "application/javascript")
            elif u.path == "/api/data":
                body = json.dumps(build_payload(parse_qs(u.query))).encode()
                self._send(200, body, "application/json")
            else:
                self._send(404, b"not found", "text/plain")
        except Exception as e:
            try:
                self._send(500, json.dumps({"error": str(e)}).encode(), "application/json")
            except Exception:
                pass


def run():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Chart page with trade audit: http://localhost:{PORT}   (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>GRAM/USDT Bot True Backtest & Chart Audit</title>
<style>
  :root {
    --bg: #090d16; --panel: #111726; --card: #151d30; --border: #232f48;
    --text: #e2e8f0; --text-dim: #94a3b8;
    --green: #10b981; --green-light: #34d399; --green-bg: rgba(16,185,129,0.15);
    --red: #f43f5e; --red-bg: rgba(244,63,94,0.15);
    --gold: #f59e0b; --gold-bg: rgba(245,158,11,0.15);
    --accent: #3b82f6; --accent-glow: rgba(59,130,246,0.25);
  }
  body{margin:0;background:var(--bg);color:var(--text);font:13px/1.45 system-ui,-apple-system,sans-serif;-webkit-font-smoothing:antialiased}
  #bar{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;padding:10px 16px;background:var(--panel);border-bottom:1px solid var(--border)}
  .group{display:inline-flex;align-items:center;gap:5px}
  input,select,button{background:#1a233a;color:var(--text);border:1px solid var(--border);border-radius:6px;padding:5px 8px;font-size:12px;transition:all 0.15s ease}
  input:focus,select:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 2px var(--accent-glow)}
  button#go{cursor:pointer;background:linear-gradient(135deg,#10b981,#059669);border:none;font-weight:700;color:#fff;padding:6px 14px;border-radius:6px;box-shadow:0 2px 6px rgba(16,185,129,0.3)}
  button#go:hover{background:linear-gradient(135deg,#34d399,#10b981)}
  
  #summary-cards {display:grid;grid-template-columns:repeat(auto-fit,minmax(125px,1fr));gap:10px;padding:10px 16px;background:var(--panel);border-bottom:1px solid var(--border)}
  .card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:8px 10px;display:flex;flex-direction:column;justify-content:center}
  .card .lbl{font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.6px;font-weight:600}
  .card .val{font-size:15px;font-weight:700;margin-top:2px}
  .c-green{color:var(--green-light)}.c-gold{color:var(--gold)}.c-blue{color:#60a5fa}.c-red{color:var(--red)}

  #chart{height:54vh}
  
  #bottom-panel{padding:12px 16px 20px;background:var(--panel);border-top:1px solid var(--border)}
  .tab-header{display:flex;gap:8px;margin-bottom:10px;border-bottom:1px solid var(--border);padding-bottom:6px}
  .tab-btn{cursor:pointer;padding:5px 12px;border-radius:6px;font-weight:600;background:transparent;border:none;color:var(--text-dim);font-size:12px}
  .tab-btn.active{background:#1e293b;color:#fff;border-bottom:2px solid var(--accent)}
  
  .tbl-wrap{max-height:28vh;overflow:auto;border:1px solid var(--border);border-radius:8px;background:var(--card)}
  table{border-collapse:collapse;width:100%;font-size:12px}
  th{position:sticky;top:0;background:#1e293b;color:var(--text);padding:8px 10px;text-align:left;border-bottom:1px solid var(--border);font-weight:600}
  td{padding:5px 10px;border-bottom:1px solid #1a233a}
  tr:hover{background:#1a233a}
  
  .badge-buy{background:var(--green-bg);color:var(--green-light);padding:2px 6px;border-radius:4px;font-weight:700;border:1px solid rgba(16,185,129,0.3)}
  .badge-sell{background:var(--gold-bg);color:var(--gold);padding:2px 6px;border-radius:4px;font-weight:700;border:1px solid rgba(245,158,11,0.3)}
  .pos-pnl{color:var(--green-light);font-weight:700}
  .neg-pnl{color:var(--red);font-weight:700}
  label{white-space:nowrap;display:inline-flex;align-items:center;gap:4px;font-size:12px;color:var(--text-dim)}
  .audit-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;padding:8px}
  .audit-box{background:#1a233a;border:1px solid var(--border);border-radius:6px;padding:12px}
  .audit-box h4{margin:0 0 8px 0;font-size:13px;color:#60a5fa;border-bottom:1px solid var(--border);padding-bottom:4px}
  .audit-row{display:flex;justify-content:space-between;padding:3px 0;font-size:12px}
</style></head><body>

<div id="bar">
  <div class="group"><label>Exchange</label><select id="exchange"><option selected>mexc</option><option>binance</option><option>bybit</option></select></div>
  <div class="group"><label>Symbol</label><input id="symbol" list="symbol-list" value="GRAM/USDT" size="11">
    <datalist id="symbol-list">
      <option value="GRAM/USDT">GRAM (Telegram)</option>
      <option value="TAO/USDT">TAO (Bittensor AI)</option>
      <option value="SOL/USDT">SOL (Solana L1)</option>
      <option value="FET/USDT">FET (ASI AI)</option>
      <option value="NOT/USDT">NOT (Notcoin)</option>
    </datalist>
  </div>
  <div class="group"><label>TF</label><select id="tf"><option value="15m">15m</option><option value="1h" selected>1h</option><option value="4h">4h</option><option value="1d">1d</option></select></div>
  <div class="group"><label>Pivot Len</label><select id="length"><option value="3">3 (Fast)</option><option value="7" selected>7 ⭐ (Halal Multi-Pair: +22.3%)</option><option value="8">8 (Balanced: +24.7%)</option><option value="10">10 (Filtered: +18.9%)</option><option value="27">27 (Standard)</option></select></div>
  <div class="group"><label>Strategy</label><select id="mode"><option value="dca2" selected>2-Tier (50% / 50%) DCA ⭐</option><option value="dca3">3-Tier (33%) DCA</option><option value="single">Single Position</option></select></div>
  <div class="group"><label><input type="checkbox" id="deeper" checked> Dip Only (Buy Deeper)</label></div>
  <div class="group"><label>Balance $</label><input id="balance" value="50" size="4"></div>
  <div class="group" style="margin-left:auto">
    <label><input type="checkbox" id="showBotTrades" checked> ⚡ <b>Bot Trades</b></label>
    <label><input type="checkbox" id="showPivots"> ▲/▼ Pivots</label>
    <label><input type="checkbox" id="showZig"> Zigzag</label>
    <button id="go">Run Backtest</button>
  </div>
</div>

<div id="summary-cards">
  <div class="card"><div class="lbl">Start Capital</div><div class="val c-blue" id="c-start">$50.00</div></div>
  <div class="card"><div class="lbl">Final Portfolio</div><div class="val c-green" id="c-final">$0.00</div></div>
  <div class="card"><div class="lbl">Net Profit</div><div class="val c-green" id="c-profit">+$0.00 (+0.0%)</div></div>
  <div class="card"><div class="lbl">Buy & Hold</div><div class="val" id="c-bh">$0.00 (+0.0%)</div></div>
  <div class="card"><div class="lbl">Time Period</div><div class="val c-blue" id="c-period">0 Days</div></div>
  <div class="card"><div class="lbl">Win Rate</div><div class="val c-gold" id="c-wr">0% (0/0)</div></div>
  <div class="card"><div class="lbl">Profit Factor</div><div class="val c-green" id="c-pf">0.00</div></div>
  <div class="card"><div class="lbl">Max Drawdown</div><div class="val c-red" id="c-dd">0.0%</div></div>
  <div class="card"><div class="lbl">Total Fees</div><div class="val" id="c-fees">$0.00</div></div>
</div>

<div id="chart"></div>

<div id="bottom-panel">
  <div class="tab-header">
    <button class="tab-btn active" id="tab-trades-btn" onclick="showTab('trades')">📋 True Bot Execution Log (Every Buy & Sell)</button>
    <button class="tab-btn" id="tab-pivots-btn" onclick="showTab('pivots')">📈 Raw LuxAlgo Pivots</button>
    <button class="tab-btn" id="tab-audit-btn" onclick="showTab('audit')">📊 Strategy Audit & Benchmark</button>
  </div>
  <div id="tbl-trades" class="tbl-wrap"></div>
  <div id="tbl-pivots" class="tbl-wrap" style="display:none"></div>
  <div id="tbl-audit" class="tbl-wrap" style="display:none"></div>
</div>

<script src="/lw.js"></script>
<script>
const $ = id => document.getElementById(id);
const chart = LightweightCharts.createChart($('chart'), {
  layout:{background:{color:'#090d16'},textColor:'#cbd5e1'},
  grid:{vertLines:{color:'#151d30'},horzLines:{color:'#151d30'}},
  timeScale:{timeVisible:true,secondsVisible:false}, crosshair:{mode:0},
  localization:{locale:'en-US'},
  autoSize:true
});
const candlesSeries = chart.addCandlestickSeries({
  upColor:'#10b981', downColor:'#f43f5e',
  borderVisible:false, wickUpColor:'#10b981', wickDownColor:'#f43f5e',
  priceFormat:{type:'price',precision:4,minMove:0.0001}
});

let lines = [], last = null;
const fmt = t => new Date(t*1000).toISOString().replace('T',' ').slice(0,16)+' UTC';

function showTab(t) {
  $('tbl-trades').style.display = t === 'trades' ? 'block' : 'none';
  $('tbl-pivots').style.display = t === 'pivots' ? 'block' : 'none';
  $('tbl-audit').style.display = t === 'audit' ? 'block' : 'none';
  $('tab-trades-btn').className = 'tab-btn' + (t === 'trades' ? ' active' : '');
  $('tab-pivots-btn').className = 'tab-btn' + (t === 'pivots' ? ' active' : '');
  $('tab-audit-btn').className = 'tab-btn' + (t === 'audit' ? ' active' : '');
}

function render() {
  if (!last) return;
  const d = last, m = [];

  // 1. True Bot Execution Markers
  if ($('showBotTrades').checked && d.bot_trades) {
    for (const bt of d.bot_trades) {
      const isBuy = bt.side === 'buy';
      m.push({
        time: bt.time,
        position: isBuy ? 'belowBar' : 'aboveBar',
        color: isBuy ? '#10b981' : '#f59e0b',
        shape: isBuy ? 'arrowUp' : 'arrowDown',
        text: isBuy ? `${bt.action} @ ${bt.price.toFixed(4)}` : `${bt.action} (${bt.pnl}) @ ${bt.price.toFixed(4)}`
      });
    }
  }

  // 2. Raw Pivot Markers
  if ($('showPivots').checked && d.regular) {
    for (const r of d.regular) {
      const buy = r.side === 'buy';
      m.push({
        time: r.time, position: buy ? 'belowBar' : 'aboveBar',
        color: buy ? '#3b82f6' : '#ec4899',
        shape: 'circle',
        text: (buy ? 'P.Low ' : 'P.High ') + r.price.toFixed(4)
      });
    }
  }

  m.sort((a,b) => a.time - b.time);
  candlesSeries.setMarkers(m);

  // Zigzag lines
  lines.forEach(s => chart.removeSeries(s)); lines = [];
  if ($('showZig').checked && d.segs) {
    const add = (t1,p1,t2,p2,dashed,color) => {
      if (t1===t2) return;
      const pts = t1<t2 ? [{time:t1,value:p1},{time:t2,value:p2}] : [{time:t2,value:p2},{time:t1,value:p1}];
      const s = chart.addLineSeries({color, lineWidth:1, lineStyle: dashed?2:0,
        lastValueVisible:false, priceLineVisible:false, crosshairMarkerVisible:false});
      s.setData(pts); lines.push(s);
    };
    for (const s of d.segs) add(s.t1,s.p1,s.t2,s.p2,s.dashed,'#334155');
  }
}

let reqId = 0;
async function load() {
  const my = ++reqId;
  const q = new URLSearchParams({
    exchange: $('exchange').value,
    symbol: $('symbol').value,
    tf: $('tf').value,
    limit: '4000',
    length: $('length').value,
    balance: $('balance').value,
    mode: $('mode').value,
    deeper: $('deeper').checked ? '1' : '0'
  });
  try {
    const r = await fetch('/api/data?' + q);
    const d = await r.json();
    if (my !== reqId) return;
    if (d.error) throw new Error(d.error);
    last = d;
    candlesSeries.setData(d.candles);

    // Update Summary Cards
    const sm = d.summary;
    $('c-start').textContent = `$${sm.initial_balance.toFixed(2)}`;
    $('c-final').textContent = `$${sm.final_balance.toFixed(2)}`;
    $('c-profit').textContent = `${sm.net_profit >= 0 ? '+' : ''}$${sm.net_profit.toFixed(2)} (${sm.pct_profit >= 0 ? '+' : ''}${sm.pct_profit.toFixed(1)}%)`;
    $('c-profit').className = 'val ' + (sm.net_profit >= 0 ? 'c-green' : 'c-red');
    $('c-bh').textContent = `$${sm.bh_final.toFixed(2)} (${sm.bh_ret >= 0 ? '+' : ''}${sm.bh_ret.toFixed(1)}%)`;
    $('c-period').textContent = `${sm.duration_days.toFixed(1)} Days (~${sm.duration_months.toFixed(1)} Mo)`;
    $('c-wr').textContent = `${sm.win_rate.toFixed(1)}% (${sm.wins}W / ${sm.losses}L)`;
    $('c-pf').textContent = `${sm.profit_factor.toFixed(2)}x`;
    $('c-dd').textContent = `${sm.max_dd.toFixed(2)}%`;
    $('c-fees').textContent = `$${sm.total_fees.toFixed(2)}`;

    // Render Bot Trades Table
    const bt = d.bot_trades || [];
    $('tbl-trades').innerHTML = '<table><tr>' +
      '<th>#</th><th>Time (UTC)</th><th>Action</th><th>Price</th><th>Tokens</th>' +
      '<th>Cash Flow</th><th>Avg Entry</th><th>Trade P&L</th><th>Cash Left</th><th>Net Worth</th></tr>' +
      bt.slice().reverse().map((t, idx) => `<tr>
        <td>${bt.length - idx}</td>
        <td>${fmt(t.time)}</td>
        <td><span class="${t.side==='buy'?'badge-buy':'badge-sell'}">${t.action}</span></td>
        <td>$${t.price.toFixed(4)}</td>
        <td>${t.tokens.toFixed(2)}</td>
        <td style="color:${t.flow>=0?'#34d399':'#f43f5e'}">${t.flow>=0?'+':''}$${t.flow.toFixed(2)}</td>
        <td>$${t.avg_entry.toFixed(4)}</td>
        <td class="${t.pnl_num>0?'pos-pnl':(t.pnl_num<0?'neg-pnl':'')}">${t.pnl}</td>
        <td>$${t.cash.toFixed(2)}</td>
        <td><b>$${t.port_val.toFixed(2)}</b></td>
      </tr>`).join('') + '</table>';

    // Render Raw Pivots Table
    const reg = d.regular || [];
    $('tbl-pivots').innerHTML = '<table><tr><th>Pivot Time</th><th>Type</th><th>Pivot Price</th><th>Confirmed Bar</th></tr>' +
      reg.slice().reverse().map(r => `<tr>
        <td>${fmt(r.time)}</td>
        <td style="color:${r.side==='buy'?'#34d399':'#f43f5e'}">${r.side==='buy'?'▲ Pivot Low':'▼ Pivot High'}</td>
        <td>$${r.price.toFixed(4)}</td>
        <td>${fmt(r.confirm_time)}</td>
      </tr>`).join('') + '</table>';

    // Render Audit Tab
    $('tbl-audit').innerHTML = `<div class="audit-grid">
      <div class="audit-box">
        <h4>Performance Overview</h4>
        <div class="audit-row"><span>Start Capital:</span><b>$${sm.initial_balance.toFixed(2)}</b></div>
        <div class="audit-row"><span>Final Portfolio:</span><b>$${sm.final_balance.toFixed(2)}</b></div>
        <div class="audit-row"><span>Net Profit:</span><b style="color:${sm.net_profit>=0?'#34d399':'#f43f5e'}">${sm.net_profit>=0?'+':''}$${sm.net_profit.toFixed(2)} (${sm.pct_profit>=0?'+':''}${sm.pct_profit.toFixed(2)}%)</b></div>
        <div class="audit-row"><span>Cash Left:</span><b>$${sm.cash_balance.toFixed(2)}</b></div>
        <div class="audit-row"><span>Tokens Remaining:</span><b>${sm.tokens_held.toFixed(2)} ($${sm.token_val.toFixed(2)})</b></div>
        <div class="audit-row"><span>Trading Fees Paid:</span><b>$${sm.total_fees.toFixed(3)}</b></div>
      </div>
      <div class="audit-box">
        <h4>Trade Statistics</h4>
        <div class="audit-row"><span>Total Completed Sells:</span><b>${sm.total_roundtrips}</b></div>
        <div class="audit-row"><span>Winning Sells:</span><b style="color:#34d399">${sm.wins}</b></div>
        <div class="audit-row"><span>Losing Sells:</span><b style="color:#f43f5e">${sm.losses}</b></div>
        <div class="audit-row"><span>Win Rate:</span><b style="color:#f59e0b">${sm.win_rate.toFixed(1)}%</b></div>
        <div class="audit-row"><span>Profit Factor:</span><b>${sm.profit_factor.toFixed(2)}x</b></div>
        <div class="audit-row"><span>Average Win:</span><b style="color:#34d399">+${sm.avg_win.toFixed(2)}%</b></div>
        <div class="audit-row"><span>Average Loss:</span><b style="color:#f43f5e">${sm.avg_loss.toFixed(2)}%</b></div>
      </div>
      <div class="audit-box">
        <h4>Risk & Benchmark Comparison</h4>
        <div class="audit-row"><span>Maximum Drawdown:</span><b style="color:#f43f5e">${sm.max_dd.toFixed(2)}%</b></div>
        <div class="audit-row"><span>Buy & Hold Return:</span><b>${sm.bh_ret>=0?'+':''}${sm.bh_ret.toFixed(2)}% ($${sm.bh_final.toFixed(2)})</b></div>
        <div class="audit-row"><span>Strategy vs Buy&Hold:</span><b style="color:#34d399">${(sm.pct_profit - sm.bh_ret)>=0?'+':''}${(sm.pct_profit - sm.bh_ret).toFixed(2)}%</b></div>
        <div class="audit-row"><span>Candles Evaluated:</span><b>${sm.candles_count}</b></div>
        <div class="audit-row"><span>Testing Start Date:</span><b>${sm.start_date}</b></div>
        <div class="audit-row"><span>Testing End Date:</span><b>${sm.end_date}</b></div>
      </div>
    </div>`;

    render();
    chart.timeScale().setVisibleLogicalRange({from: Math.max(0, d.candles.length - 200), to: d.candles.length + 5});
  } catch(e) {
    if (my !== reqId) return;
    alert('Error: ' + e.message);
  }
}

$('go').onclick = load;
['showBotTrades','showPivots','showZig'].forEach(id => $(id).onchange = render);
load();
</script></body></html>
"""

if __name__ == "__main__":
    run()
