import os
import discord
from discord.ext import tasks, commands
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID"))
CHECK_CHANNEL_NAME = "discussion-💬"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Bot connected as {bot.user}")
    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        print("Guild not found.")
    else:
        print(f"Connected to guild: {guild.name}")
    check_inactive_members.start()


@tasks.loop(hours=24)
async def check_inactive_members():
    print("Running daily inactivity check...")
    now = datetime.now(timezone.utc)
    warning_cutoff = now - timedelta(days=90)
    kick_cutoff = now - timedelta(days=180)

    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        print("Guild not found.")
        return

    discussion_channel = discord.utils.get(guild.text_channels, name=CHECK_CHANNEL_NAME)
    if discussion_channel is None:
        print(f"Channel '{CHECK_CHANNEL_NAME}' not found.")
        return

    for member in guild.members:
        if member.bot:
            continue

        roles = [role.name for role in member.roles]

        # Protect Generals and Majors
        if "General 🪽" in roles or "Major 🎖️" in roles:
            continue

        # Fetch user message history to determine last activity
        last_active = None
        for channel in guild.text_channels:
            try:
                async for msg in channel.history(limit=100):
                    if msg.author == member:
                        if last_active is None or msg.created_at > last_active:
                            last_active = msg.created_at
            except:
                continue

        if last_active is None:
            last_active = member.joined_at or now  # fallback to join date if no messages

        # Ensure last_active is timezone aware
