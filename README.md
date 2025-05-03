# 📦 Discord Cleaner Bot

A Discord bot that automatically assigns the "Cleaner" role to members who have been inactive (no messages or voice activity) for over 90 days. It also removes all other roles except "Soldier".

## Features

-	Assigns the @Cleaner role to users inactive for ≥ 3 months
-	Posts a public warning message in #discussion-💬
-	Removes all roles except @Soldier
-	Kicks @Cleaner users after 6 months total inactivity
-	Exempts @Major and @General roles from being kicked

## Setup

### 1. Prerequisites

- Python 3.9+
- A Discord bot registered at https://discord.com/developers/applications
- Bot must have permissions:
  - Manage Roles
  - Kick Members
  - Read Message History
  - View Channels
  - Connect

### 2. Clone and Install

```bash
git clone https://github.com/bjoerrrn/discord-cleaner-bot.git
cd discord-cleaner-bot
pip install -r requirements.txt
```


### 3. Create and activate a virtual environment

```
sudo apt install python3-venv
python3 -m venv venv
source venv/bin/activate
```

### 4. Install required packages

```
pip install discord.py python-dotenv
```

### 5. Configure

Create a `.env` file:
```
touch .env
```

```
DISCORD_TOKEN=your-bot-token-here
DISCORD_GUILD_ID=123456789012345678
```

### 6. Enable the bot to run daily

Add this to your crontab (crontab -e):

```bash
0 0 * * * cd /home/pi/discord-cleaner-bot && /home/pi/discord-cleaner-bot/venv/bin/python bot.py >> bot.log 2>&1
```

### 7. 🤖 Registering Your Discord Bot
1.	Go to the Discord Developer Portal
2.	Click “New Application”
3.	Name it (e.g., CleanerBot)
4.	Under “Bot”, click “Add Bot”
5.	Click “Reset Token” → Copy this and paste it into your .env as DISCORD_TOKEN

### 8. 🧾 Inviting the Bot to Your Server
1.	In the Developer Portal, under OAuth2 > URL Generator:
-	Scopes: bot
- Bot Permissions: Read Messages/View Channels, Send Messages, Manage Roles, Kick Members
2.	Copy the generated URL and open it in your browser to invite the bot.

### 9. 🔍 How to Get Your DISCORD_GUILD_ID
1.	In Discord, go to User Settings > Advanced → Enable Developer Mode
2.	Right-click your server icon → Copy Server ID
3.	Paste it into .env as DISCORD_GUILD_ID


## Notes

- The bot only sees message history in channels it has access to.
- Voice presence is limited to current online status.
- Extend with a database if you want full tracking history.

MIT License
