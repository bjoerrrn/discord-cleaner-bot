# Discord Cleaner Bot

A Discord bot that automatically assigns the "Cleaner" role to members who have been inactive (no messages or voice activity) for over 90 days. It also removes all other roles except "Soldier".

## Features

- Daily scan of all members
- Marks completely inactive members as "Cleaner"
- Retains "Soldier" role for all
- Lightweight and runs on Raspberry Pi
- Public warning message in `#discussion-💬` when members are marked as inactive
- Automatic kick after 180 days of inactivity
- Generals and Majors are exempt from being kicked

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

### 3. Configure

Create a `.env` file:

```
DISCORD_TOKEN=your-bot-token-here
DISCORD_GUILD_ID=123456789012345678
```

### 4. Run the Bot

```bash
python bot.py
```

---

### Optional: Run via Cron

```bash
crontab -e
```

Add this:

```bash
0 0 * * * cd /home/pi/discord-cleaner-bot && /usr/bin/python3 bot.py >> log.txt 2>&1
```

---

## Notes

- The bot only sees message history in channels it has access to.
- Voice presence is limited to current online status.
- Extend with a database if you want full tracking history.

MIT License
