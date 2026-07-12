# 🌟 Improve Your English — Telegram Bot

An automated Telegram bot that posts emoji-rich English lessons and interactive tests to a channel on a schedule.

## ✨ Features

- 📚 **6 Lessons Daily** — every 4 hours
- 🧪 **2 Tests Daily** — every 12 hours with interactive buttons
- 🔄 **Smart Topic Rotation** — no repeats for 36 posts
- 🤖 **AI-Powered Content** — uses OpenRouter API
- 🎨 **Emoji-Rich Formatting** — visually engaging, premium post styling
- ⏰ **Automatic Scheduling** — fully hands-off operation

## 🚀 Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure your settings in `config.py`:
   - 🔑 Bot Token
   - 📢 Channel ID
   - 🔐 OpenRouter API Key

3. Run the bot:
```bash
python bot.py
```

## 📋 Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | 🌟 Welcome message |
| `/help` | 📋 Show available commands |
| `/status` | 📊 Check bot statistics |
| `/lesson` | 📚 Get a lesson immediately |
| `/test` | 🧪 Get a test immediately |
| `/reset` | 🔄 Reset topic history |

## ⏰ Schedule

| Content Type | Frequency | Daily Count |
|--------------|-----------|-------------|
| 📚 Lessons | Every 4 hours | 6 posts |
| 🧪 Tests | Every 12 hours | 2 posts |

## 🎨 Design

- 🎯 **Emoji-rich content** — AI generates lessons with tasteful, relevant emojis
- 🧪 **Interactive tests** — emoji-labeled buttons (🅰️ 🅱️ ©️) for engagement
- 📝 **Clean hashtags** — CamelCase hashtags without emojis (e.g., `#PresentPerfectTense`)
- 🖼 **Premium visual hierarchy** — structured posts with dividers and clear sections

## 📦 Requirements

- Python 3.8+
- apscheduler
- python-dotenv

## 📄 License

MIT License