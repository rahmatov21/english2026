"""
Portfolio Viewer & Telegram Integration for Halal Crypto Auto-Trader
Fetches live prices, reads trader state, and formats real-time portfolio summaries for Telegram.
"""

import json
import os
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parent
TRADER_DIR = ROOT_DIR / "files (5)"

if not TRADER_DIR.exists():
    for candidate in ROOT_DIR.iterdir():
        if candidate.is_dir() and (candidate / "luxalgo.py").exists() and (candidate / "bot.py").exists():
            TRADER_DIR = candidate
            break

ADMIN_CHAT_FILE = ROOT_DIR / "admin_chats.json"


def save_subscriber_chat_id(chat_id: int | str):
    """Save user chat ID so they receive real-time trade alerts."""
    try:
        chats = set()
        if ADMIN_CHAT_FILE.exists():
            with open(ADMIN_CHAT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    chats = set(data)
        chats.add(str(chat_id))
        with open(ADMIN_CHAT_FILE, "w", encoding="utf-8") as f:
            json.dump(list(chats), f)
    except Exception as e:
        print(f"Error saving chat ID: {e}")


def get_subscriber_chat_ids() -> list:
    """Get list of chat IDs to notify for trades."""
    chats = set()
    env_admin = os.getenv("ADMIN_CHAT_ID", os.getenv("TELEGRAM_CHAT_ID", ""))
    if env_admin:
        for cid in env_admin.split(","):
            if cid.strip():
                chats.add(cid.strip())

    if ADMIN_CHAT_FILE.exists():
        try:
            with open(ADMIN_CHAT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    chats.update(str(c) for c in data)
        except Exception:
            pass

    return list(chats)


def fetch_live_mexc_price(symbol: str) -> float:
    """Fetch real-time ticker price from MEXC public API (no key needed)."""
    clean_sym = symbol.replace("/", "").replace("_", "").upper()
    url = f"https://api.mexc.com/api/v3/ticker/price?symbol={clean_sym}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return float(data.get("price", 0.0))
    except Exception:
        return 0.0


def get_trader_state() -> tuple[dict, Path | None]:
    """Find and load the trader state JSON file."""
    mode = os.getenv("MODE", "paper").lower()
    candidate_files = [
        TRADER_DIR / f"state_{mode}.json",
        TRADER_DIR / "state_paper.json",
        TRADER_DIR / "state_live.json",
        ROOT_DIR / f"state_{mode}.json",
        ROOT_DIR / "state_paper.json",
    ]
    for path in candidate_files:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f), path
            except Exception:
                pass
    return {}, None


def format_portfolio_message() -> tuple[str, dict]:
    """Generate an emoji-rich, formatted Telegram message of the current trading portfolio."""
    st, path = get_trader_state()
    mode = os.getenv("MODE", "paper").upper()

    if not st:
        text = (
            "📊 <b>Halal Crypto Trader Portfolio</b>\n\n"
            "⚠️ <i>No active trading state found yet.</i>\n"
            "The trading bot is starting up or waiting for the first cycle.\n\n"
            "Please check again in a few moments! ⏳"
        )
        keyboard = {"inline_keyboard": [[{"text": "🔄 Refresh", "callback_data": "refresh_portfolio"}]]}
        return text, keyboard

    free_cash = float(st.get("paper_usdt", 0.0))
    total_realized_pnl = float(st.get("total_pnl_usdt", 0.0))
    pairs_data = st.get("pairs", {})

    holdings_text_parts = []
    total_holdings_val = 0.0
    total_unrealized_pnl_usdt = 0.0

    for sym, p_state in pairs_data.items():
        base = sym.split("/")[0]
        held_tokens = float(p_state.get("tokens", 0.0))
        buy_tier = int(p_state.get("buy_tier", 0))
        sell_calls = int(p_state.get("sell_calls", 0))
        entry_lots = p_state.get("entry_lots", [])

        # Fetch current live price
        live_px = fetch_live_mexc_price(sym)
        if live_px == 0.0 and "last_prices" in st:
            live_px = float(st.get("last_prices", {}).get(sym, 0.0))

        if held_tokens > 0:
            tot_cost = sum(l.get("cost", 0.0) for l in entry_lots)
            tot_tok = sum(l.get("tokens", 0.0) for l in entry_lots)
            avg_entry = tot_cost / tot_tok if tot_tok > 0 else live_px

            cur_val = held_tokens * live_px
            total_holdings_val += cur_val

            unrealized_pnl_usdt = cur_val - tot_cost
            total_unrealized_pnl_usdt += unrealized_pnl_usdt
            pnl_pct = (live_px / avg_entry - 1) * 100 if avg_entry > 0 else 0.0
            pnl_emoji = "🟢" if pnl_pct >= 0 else "🔴"

            part = (
                f"• <b>{sym}:</b>\n"
                f"  ├ 📦 Tokens: <b>{held_tokens:.2f} {base}</b> (${cur_val:.2f})\n"
                f"  ├ 🎯 Buy Tier: <b>{buy_tier}/2</b> | Sells: <b>{sell_calls}/2</b>\n"
                f"  ├ 📥 Avg Entry: <code>${avg_entry:.4f}</code>\n"
                f"  ├ 📊 Current Price: <code>${live_px:.4f}</code>\n"
                f"  └ {pnl_emoji} Unrealized P&L: <b>{pnl_pct:+.2f}%</b> ({unrealized_pnl_usdt:+.2f} USDT)"
            )
        else:
            part = (
                f"• <b>{sym}:</b>\n"
                f"  ├ 📦 Tokens: <b>0.00 {base}</b> (100% Cash) 💵\n"
                f"  ├ 🎯 Buy Tier: <b>0/2</b> | Ready for signal\n"
                f"  └ 📊 Current Price: <code>${live_px:.4f}</code>"
            )
        holdings_text_parts.append(part)

    net_worth = free_cash + total_holdings_val
    realized_sign = "+" if total_realized_pnl >= 0 else ""
    now_str = datetime.now().strftime("%H:%M:%S")

    holdings_section = "\n\n".join(holdings_text_parts) if holdings_text_parts else "<i>No pairs configured</i>"

    message = f"""📊 <b>Halal Crypto Portfolio (MEXC Spot)</b>

💼 <b>Trading Mode:</b> <code>{mode}</code>
💰 <b>Total Net Worth:</b> <b>${net_worth:.2f} USDT</b>
💵 <b>Free Cash:</b> ${free_cash:.2f} USDT
📈 <b>Realized P&L:</b> <b>{realized_sign}${total_realized_pnl:.2f} USDT</b>

━━━━━━━━━━━━━━━━━━━━━
🪙 <b>Pair Status & Positions:</b>

{holdings_section}

━━━━━━━━━━━━━━━━━━━━━
🤖 <b>Status:</b> 🟢 Active & Monitoring 1h Candles
⏱️ <i>Updated at {now_str} (Real-Time)</i>"""

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🔄 Refresh Portfolio", "callback_data": "refresh_portfolio"},
            ],
            [
                {"text": "📚 English Lesson", "callback_data": "singletest_poll"},
                {"text": "🧪 Take Test", "callback_data": "singletest_inline"},
            ]
        ]
    }

    return message, keyboard


def send_telegram_trade_alert(bot_token: str, message: str):
    """Send trade execution alert to all registered admin chats."""
    if not bot_token or bot_token == "your_bot_token_here":
        return

    chat_ids = get_subscriber_chat_ids()
    channel_id = os.getenv("CHANNEL_ID", "")

    # Combine unique recipients
    targets = set(chat_ids)
    if channel_id and channel_id.startswith("@"):
        targets.add(channel_id)

    for cid in targets:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = json.dumps({
            "chat_id": cid,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10):
                pass
        except Exception as e:
            print(f"Failed to send trade alert to {cid}: {e}")
