# 📦 Discord Cleaner Bot

A Discord bot that automatically assigns the "Cleaner" role to members who have been inactive (no messages or voice activity) for over 90 days. It also removes all other roles except "Soldier", and kicks them after 180 days.

## Features

- Assigns the @Cleaner role to users inactive for ≥ 3 months
- Posts a public warning message in #discussion-💬
- Removes all roles except @Soldier
- Kicks @Cleaner users after 6 months total inactivity
- Exempts @Major and @General roles from being kicked
- Posts original role list for admin reference

## 📦 Installation & Setup

### 1. Prerequisites

- Python 3.9+
- A registered Discord bot: https://discord.com/developers/applications
- The bot must have the following permissions:
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

### 6. Registering Your Bot in Discord

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click “New Application” and give it a name
3. Under “Bot”, click “Add Bot”
4. Click “Reset Token” → Copy this token and add it to your `.env`

### 7. Invite the Bot to Your Server

1. In the Developer Portal, go to `OAuth2 > URL Generator`
2. Under scopes, select:
   - `bot`
3. Under Bot Permissions, select:
   - Read Messages/View Channels
   - Send Messages
   - Manage Roles
   - Kick Members
4. Copy the generated URL and open it in your browser to invite the bot

### 8. Get Your Discord Guild (Server) ID

1. In Discord: `User Settings > Advanced > Enable Developer Mode`
2. Right-click your server icon → Click "Copy Server ID"
3. Paste this ID into the `.env` file as `DISCORD_GUILD_ID`

---

## 🔁 Run the Bot Automatically with systemd

### 1. Create a systemd Service File

```bash
sudo nano /etc/systemd/system/discord-cleaner.service
```

Paste the following, updating paths as needed:

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

## 📝 Notes

- The bot checks up to 100 messages per text channel for each user.
- Voice channel presence resets inactivity counter.
- The original roles removed are listed in the `#discussion-💬` warning post.
- Admins can use this to manually restore roles if needed.

---

MIT License
