# idstickbot — Sticker & Custom Emoji ID Bot

<p align="center">
  <b>Telegram bot that instantly replies with <code>file_id</code> for stickers and <code>custom_emoji_id</code> for Premium emoji.</b><br>
  Tap-to-copy, no fluff — built for developers, sticker makers, and bot builders.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/aiogram-3.30-2CA5E0?style=flat-square&logo=telegram&logoColor=white" alt="aiogram">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey?style=flat-square" alt="Platform">
  <a href="https://t.me/idstickrobot"><img src="https://img.shields.io/badge/Telegram-@idstickrobot-26A5E4?style=flat-square&logo=telegram&logoColor=white" alt="Telegram"></a>
</p>

---

## ✨ Features

| Feature | What you get |
|---|---|
| **Sticker IDs** | `file_id`, `file_unique_id`, `set_name`, `emoji`, `custom_emoji_id` (if type `custom_emoji`) |
| **Premium Emoji IDs** | `custom_emoji_id` + default emoji for any message / caption containing Premium emoji |
| **Copy-friendly** | Every ID in its own `<code>` block — one tap to copy on mobile/desktop |
| **Smart parsing** | Correct UTF-16 handling for surrogate pairs, deduplication, per-field entity resolution |
| **Reply Keyboard** | Persistent keyboard — 🎨 Sticker Guide, ✨ Emoji Guide, ℹ️ About, ❌ Hide |
| **Silent by design** | No spam — custom emoji handler silent, plain text gently guided only in PM |
| **Production ready** | Rotating logs, graceful shutdown, HTML escaping, `/help` + BotFather menu |

Supported sticker kinds: `Static` · `Animated (.tgs)` · `Video (.webm)` · `Custom Emoji`

---

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/algorithco/idstickbot.git
cd idstickbot

# 2. Environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# then edit .env and set your token from @BotFather

# 4. Run
python bot.py
```

Open Telegram → talk to your bot → send a sticker or a Premium emoji.

---

## ⚙️ Configuration

### `.env`

```env
# Get a token from @BotFather → /newbot
BOT_TOKEN=123456789:AAA-your-botfather-token-here

# Optional — drop queued updates on restart (default: false)
DROP_PENDING_UPDATES=false
```

| Variable | Required | Default | Description |
|---|:---:|---|---|
| `BOT_TOKEN` | ✅ | — | Bot token from `@BotFather` |
| `DROP_PENDING_UPDATES` | — | `false` | `true` = discard updates received while offline |

> Token is read with `(os.getenv("BOT_TOKEN") or "").strip()` — whitespace is ignored and missing token exits with a clear message.

---

## 💬 Usage

### Reply Keyboard

After `/start` a persistent keyboard appears:

| Button | Action |
|---|---|
| `🎨 Sticker Guide` | Step-by-step how to get `file_id` / `file_unique_id` / `set_name` |
| `✨ Emoji Guide` | How to get `custom_emoji_id` from Premium emoji |
| `ℹ️ About` | About + inline buttons → GitHub / Share bot |
| `❌ Hide Keyboard` | Removes keyboard (`/start` brings it back) |

The keyboard is `resize_keyboard` + `is_persistent` with placeholder `Send a sticker or Premium emoji…` — hidden via `ReplyKeyboardRemove` on demand.

### Commands

| Command | Description |
|---|---|
| `/start` | Show help + reply keyboard |
| `/help` | Alias for `/start` |

### Sticker

Send any sticker — the bot replies threaded (new design):

```
🎬 Video sticker
file_id:
<code>CAACAgIAAxkBAAEf...</code>

file_unique_id:
<code>AgADr...</code>

Set: <code>MySetByBot</code>
Emoji: 😀
Tap any code block to copy 📋
```

- Includes `file_unique_id` (stable across bots) and `set_name` to fetch the whole set via `getStickerSet`.
- Works with forwarded stickers and all types.

### Premium Custom Emoji

Send any message or caption containing Premium emoji (including photo captions):

```
✨ Custom emoji IDs — tap to copy:
😀 <code>5368324170671202286</code>
❤️ <code>5431449001532594346</code>
```

- Deduplicates same `custom_emoji_id` in one message (first-seen order).
- Correctly resolves text vs. caption offsets — even with emoji like `🏳️‍🌈` or `😀` that use surrogate pairs.

### Plain Text

In private chats, other text gets a gentle hint with the keyboard; groups stay silent to avoid spam. Buttons are handled before the fallback.

---

## 📁 Project Structure

```
idstickbot/
├── bot.py              # Main bot — handlers, UTF-16 parsing, formatting
├── requirements.txt    # aiogram, python-dotenv
├── .env.example        # Template for BOT_TOKEN
├── .env                # Your real token (gitignored)
├── run.bat             # Windows auto-restart loop
├── bot.log             # Rotating log (5 MB × 5, gitignored)
└── restart.log         # Restart history (gitignored)
```

---

## 🧠 How It Works

### UTF-16 entity handling

Telegram sends `offset`/`length` in UTF-16 code units, not Python characters. A naive `text[offset:offset+length]` breaks on `😀` (2 units) or ZWJ sequences.

```python
raw = text.encode("utf-16-le")
units = len(raw) // 2
chunk = raw[offset*2 : (offset+length)*2]
char = chunk.decode("utf-16-le")
```

Bounds are checked before slicing, and text vs. caption entities are resolved against their own field to avoid offset mismatch.

### Why `<code>` blocks?

Telegram clients make `<code>...</code>` tappable. One ID per block = one tap copies exactly that ID — no selection dance.

```python
f"<code>{html.escape(file_id)}</code>"
```

All user-visible strings are `html.escape`d for `ParseMode.HTML` safety.

---

## 🖥️ Deployment

### Windows — `run.bat` (recommended)

`run.bat` loops forever and logs restarts:

```bat
@echo off
cd /d "%~dp0"
:loop
echo [%date% %time%] Starting bot...>> restart.log
".venv\Scripts\python.exe" bot.py
echo [%date% %time%] Bot exited code %errorlevel% >> restart.log
timeout /t 5 /nobreak >nul
goto loop
```

**Manual start (hidden):**

```powershell
Start-Process -FilePath ".\run.bat" -WindowStyle Hidden
Get-Content bot.log -Tail 20
```

**Auto-start at logon (no admin needed):**

Already configured via:

- Registry: `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` → `IDStickBot`
- Startup shortcut: `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\IDStickBot.lnk`

**Scheduled Task (admin, survives reboot before logon):**

```powershell
# Run as Administrator
$A = New-ScheduledTaskAction -Execute "C:\path\to\idstickbot\run.bat" -WorkingDirectory "C:\path\to\idstickbot"
$T = @((New-ScheduledTaskTrigger -AtStartup),(New-ScheduledTaskTrigger -AtLogOn))
$S = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0 -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$P = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Highest
Register-ScheduledTask -TaskName IDStickBot -Description "idstickbot polling" -Action $A -Trigger $T -Settings $S -Principal $P -Force
```

### Linux / macOS — systemd

```ini
# /etc/systemd/system/idstickbot.service
[Unit]
Description=idstickbot
After=network.target

[Service]
WorkingDirectory=/opt/idstickbot
ExecStart=/opt/idstickbot/.venv/bin/python bot.py
Restart=always
RestartSec=5
EnvironmentFile=/opt/idstickbot/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now idstickbot
journalctl -u idstickbot -f
```

### Docker (optional)

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py .env.example ./
CMD ["python", "bot.py"]
```

---

## 📝 Logs

- **File:** `bot.log` via `RotatingFileHandler` — `5 MB × 5` (`bot.log`, `bot.log.1` …), UTF-8, also mirrored to console.
- **Format:** `%(asctime)s %(levelname)-8s %(name)s - %(message)s`
- **Restart history:** `restart.log` (only when using `run.bat`)
- Both are `.gitignore`d.
- Log level `INFO` — every handled update is logged by `aiogram.dispatcher`.

Tail logs:

```powershell
Get-Content bot.log -Tail 50 -Wait
Get-Content restart.log -Tail 20
```

---

## 🛠️ Development

```bash
# Lint / type check (optional)
pip install ruff mypy
ruff check bot.py
mypy bot.py

# Quick smoke test
python -m py_compile bot.py
python -c "import bot; print(bot.extract_custom_emojis)"
```

**Environment:** Python 3.12, `aiogram 3.30`, `python-dotenv 1.2.3`  
Pin exact versions for reproducibility: `pip freeze > requirements.lock`

---

## 🔒 Security Notes

- **Never commit `.env`** — `.gitignore` covers `.env`, `.env.*`, `*.env` (`.env.example` is the only exception).
- **OneDrive / cloud sync:** If the project lives under `OneDrive\Desktop`, `.env` is synced to the cloud. Consider moving to `C:\Projects\...` or excluding `.env` from sync, and rotate the token via `@BotFather` → `/mybots` → `API Token` → `Revoke` if exposed.
- All IDs are escaped before sending with `ParseMode.HTML`.

---

## 🤝 Contributing

PRs welcome — keep the scope tight (sticker / emoji IDs). For larger features open an issue first.

1. Fork & create a branch
2. `python -m py_compile bot.py` must pass
3. Commit with a clear message and push

---

## 📄 License

MIT — do what you want, just keep the notice.

---

<p align="center">
  Made with ❤️ for Telegram bot developers<br>
  <a href="https://t.me/idstickrobot">@idstickrobot</a> · <a href="https://github.com/algorithco/idstickbot">algorithco/idstickbot</a>
</p>
