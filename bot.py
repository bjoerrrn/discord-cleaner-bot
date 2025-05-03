import os
import discord
from discord.ext import tasks, commands
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID"))
CLEANER_ROLE_NAME = "Cleaner"
SOLDIER_ROLE_NAME = "Soldier"
EXEMPT_ROLES = [CLEANER_ROLE_NAME, SOLDIER_ROLE_NAME, "Major", "General"]
WARNING_CHANNEL_NAME = "discussion-💬"

intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.guilds = True
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot connected as {bot.user}")
    check_inactive_members.start()

@tasks.loop(hours=24)
async def check_inactive_members():
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        print("Guild not found.")
        return

    now = datetime.now(timezone.utc)
    inactive_cutoff = now - timedelta(days=90)
    kick_cutoff = now - timedelta(days=180)
    warning_channel = discord.utils.get(guild.text_channels, name=WARNING_CHANNEL_NAME)

    for member in guild.members:
        if member.bot:
            continue

        member_roles = [r.name for r in member.roles]
        if "Major" in member_roles or "General" in member_roles:
            continue

        last_active = None

        for channel in guild.text_channels:
            try:
                async for msg in channel.history(limit=100):
                    if msg.author == member:
                        if not last_active or msg.created_at > last_active:
                            last_active = msg.created_at
                        break
            except discord.Forbidden:
                continue

        if member.voice and member.voice.channel:
            last_active = now

        if not last_active:
            last_active = datetime.utcfromtimestamp(0)

        if last_active < kick_cutoff:
            try:
                await member.kick(reason="Inactive for more than 180 days")
                print(f"Kicked: {member.name}")
            except discord.Forbidden:
                print(f"No permission to kick {member.name}")
            continue

        if last_active < inactive_cutoff:
            roles_to_remove = [r for r in member.roles if r.name not in EXEMPT_ROLES and r != guild.default_role]
            cleaner_role = discord.utils.get(guild.roles, name=CLEANER_ROLE_NAME)
            soldier_role = discord.utils.get(guild.roles, name=SOLDIER_ROLE_NAME)

            try:
                if roles_to_remove:
                    await member.remove_roles(*roles_to_remove, reason="Marked inactive")
                if cleaner_role and cleaner_role not in member.roles:
                    await member.add_roles(cleaner_role, reason="Inactive 90+ days")
                    if warning_channel:
                        await warning_channel.send(f"{member.mention}, you have been marked as inactive and moved to the 'Cleaner' role. Please become active to avoid removal.")
                if soldier_role and soldier_role not in member.roles:
                    await member.add_roles(soldier_role, reason="Maintain Soldier role")
                print(f"Updated: {member.name}")
            except discord.Forbidden:
                print(f"No permission to update roles for {member.name}")

bot.run(TOKEN)
