# Discord Cleaner Bot

A Discord bot that automatically assigns the "Cleaner" role to members who have been inactive (no messages or voice activity) for over 90 days. It also removes all other roles except "Soldier", and kicks them after 180 days.

## Features

- Assigns the @Cleaner role to users inactive for ≥ 3 months
- Removes all roles except @Soldier
- Posts a warning in #discussion-💬 when roles are changed
- Posts original roles in the same channel for admin reference
- Kicks @Cleaner users after 6 months of inactivity
- Exempts @Major and @General roles from being kicked
- Activity cache improves performance and avoids repeated scanning
- Commands for status reports, exporting activity, and debugging
- Systemd integration for auto-start and log viewing

## 📦 Installation & Setup

### 1. Prerequisites

- Python 3.9+
- A registered Discord bot: https://discord.com/developers/applications
- The bot must have these permissions:
  - Manage Roles
  - Kick Members
  - Read Message History
  - View Channels
  - Connect to Voice Channels

### 2. Clone the Repository

```bash
git clone https://github.com/bjoerrrn/discord-cleaner-bot.git
cd discord-cleaner-bot
```

### 3. Create and Activate a Virtual Environment

```bash
sudo apt install python3-venv
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Python Dependencies

```bash
pip install -r requirements.txt
```

If no `requirements.txt` is available, install manually:

```bash
pip install discord.py python-dotenv
```

### 5. Configure Your Environment

Create a `.env` file in the root directory:

```env
DISCORD_TOKEN=your-bot-token-here
DISCORD_GUILD_ID=123456789012345678
```

### 6. Register Your Bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click “New Application” → Name it
3. Under “Bot” → “Add Bot”
4. Click “Reset Token” → Add it to your `.env`

### 7. Invite the Bot to Your Server

1. In the Developer Portal → `OAuth2 > URL Generator`
2. Scopes: `bot`
3. Bot Permissions:
   - Read Messages/View Channels
   - Send Messages
   - Manage Roles
   - Kick Members
4. Open the generated URL to invite the bot

### 8. Get Your Server (Guild) ID

1. Enable Developer Mode in Discord: `User Settings > Advanced`
2. Right-click server icon → “Copy Server ID”
3. Paste into `.env` as `DISCORD_GUILD_ID`

---

## 🔁 Run the Bot Automatically with systemd

### 1. Create a systemd Service

```bash
sudo nano /etc/systemd/system/discord-cleaner.service
```

Paste and edit paths:

```ini
[Unit]
Description=Discord Cleaner Bot
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/discord-cleaner-bot
ExecStart=/home/pi/discord-cleaner-bot/venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### 2. Enable and Start the Service

```bash
sudo systemctl daemon-reexec
sudo systemctl daemon-reload
sudo systemctl enable discord-cleaner
sudo systemctl start discord-cleaner
```

### 3. View Logs

```bash
journalctl -u discord-cleaner -f
```

---

## 🛠️ Bot Commands

Only members with the @General role can run these:

- `!commands` – Lists all available commands
- `!lastactive @member` – Shows last message, voice, and join date
- `!exportactivity` – CSV export of activity and roles
- `!unreadable_channels` – Lists channels the bot can't read
- `!inactivity_report` – Lists all users and last activity
- `!inactivity_report clean` – Only users near kick/cleaner thresholds

---

## 🔍 Behavior Details

- Scans 5000 messages per channel to build the activity cache
- Voice channel activity updates cache automatically
- Messages and voice tracked across all readable channels
- Posts notifications in #discussion-💬 with embedded formatting
- Kick logic is currently disabled (commented out)
- All timestamps in UTC

---

MIT License
