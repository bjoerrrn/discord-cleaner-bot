import os
import discord
from discord.ext import tasks, commands
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID"))
GENERAL_ROLE_ID = 1269752542515040477
STAFF_CHANNEL_ID = 1194194222702661632

CLEANER_ROLE_NAME = "Cleaner"
SOLDIER_ROLE_NAME = "Soldier"
EXEMPT_ROLES = ["Major", "General"]
WARNING_CHANNEL_NAME = "discussion-💬"

intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.guilds = True
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


def create_embed(title: str, description: str, color=discord.Color.orange()):
    return discord.Embed(title=title, description=description, color=color)


@bot.event
async def on_ready():
    print(f"Bot connected as {bot.user}")
    check_inactive_members.start()


@bot.event
async def on_command_error(ctx, error):
    staff_channel = bot.get_channel(STAFF_CHANNEL_ID)
    if staff_channel:
        embed = create_embed(
            title="Command Error ❌",
            description=f"Error: `{str(error)}`\nCommand: `{ctx.message.content}`",
            color=discord.Color.red()
        )
        await staff_channel.send(embed=embed)
    else:
        print("Staff channel not found for error reporting.")


@bot.command()
async def test_embed(ctx):
    embed = create_embed(
        title="Test Embed Message 🧹",
        description=(
            f"Attention {ctx.author.mention}, this is a formatting test for the Cleaner bot.\n"
            f"`Cleaner` role would be assigned here if you were inactive.\n"
            f"For Admin's reference: Original roles before cleanup: `Tester, Demo`"
        )
    )
    await ctx.send(embed=embed)
    
    
@bot.command()
async def unreadable_channels(ctx):
    """Lists all text channels the bot cannot read."""
    if not any(role.id == GENERAL_ROLE_ID for role in ctx.author.roles):
        await ctx.send("❌ You do not have permission to use this command.")
        return

    guild = bot.get_guild(GUILD_ID)
    unreadable = []
    for channel in guild.text_channels:
        if not channel.permissions_for(guild.me).read_messages:
            unreadable.append(channel.name)

    if not unreadable:
        await ctx.send("✅ Bot can read all text channels.")
    else:
        await ctx.send(
            f"⚠️ Cannot read these channels:\n" + "\n".join(f"• #{name}" for name in unreadable)
        )
    
    
@bot.command()
async def debug_cleaner_check(ctx):
    if not any(role.id == GENERAL_ROLE_ID for role in ctx.author.roles):
        await ctx.send("❌ You do not have permission to use this command.")
        return

    guild = bot.get_guild(GUILD_ID)
    if not guild:
        await ctx.send("Guild not found.")
        return

    now = datetime.now(timezone.utc)
    kick_cutoff = now - timedelta(days=180)
    overdue_cleaners = []

    for member in guild.members:
        if member.bot:
            continue

        member_roles = [r.name for r in member.roles]
        if CLEANER_ROLE_NAME not in member_roles:
            continue

        last_active = None
        used_voice_as_activity = False

        # Try to find last message
        for channel in guild.text_channels:
            try:
                async for msg in channel.history(limit=5000):
                    if msg.author == member:
                        if not last_active or msg.created_at > last_active:
                            last_active = msg.created_at
                        break
            except discord.Forbidden:
                continue

        # Fallback to voice activity
        if member.voice and member.voice.channel:
            last_active = now
            used_voice_as_activity = True

        # Fallback to join date or 1970
        if not last_active:
            last_active = member.joined_at or datetime(1970, 1, 1, tzinfo=timezone.utc)

        if last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=timezone.utc)

        days_inactive = (now - last_active).days

        if last_active < kick_cutoff:
            overdue_days = days_inactive - 180
            overdue_cleaners.append({
                "name": member.display_name,
                "days_inactive": days_inactive,
                "overdue_by": overdue_days,
                "last_active": last_active.strftime('%Y-%m-%d %H:%M UTC'),
                "used_voice": used_voice_as_activity
            })

    if not overdue_cleaners:
        await ctx.send("✅ No overdue Cleaners found. All is working as expected.")
        return

    chunks = [overdue_cleaners[i:i + 10] for i in range(0, len(overdue_cleaners), 10)]
    for chunk in chunks:
        description = "**Overdue Cleaners (not yet kicked):**\n"
        for user in chunk:
            voice_note = "🎙️ Voice" if user["used_voice"] else "💬 Text/Join"
            description += (
                f"• `{user['name']}` — `{user['days_inactive']}d` inactive, "
                f"`{user['overdue_by']}d` overdue\n"
                f"   ↳ Last active: `{user['last_active']}` ({voice_note})\n"
            )

        embed = create_embed(
            title="🔍 Debug: Cleaner Kick Check",
            description=description,
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)


@bot.command()
async def inactivity_report(ctx):
    if not any(role.id == GENERAL_ROLE_ID for role in ctx.author.roles):
        await ctx.send("❌ You do not have permission to use this command.")
        return

    guild = bot.get_guild(GUILD_ID)
    if not guild:
        await ctx.send("Guild not found.")
        return

    now = datetime.now(timezone.utc)
    inactive_cutoff = now - timedelta(days=90)
    kick_cutoff = now - timedelta(days=180)

    nearing_inactive = []
    overdue_cleaners = []
    cleaners_soon_kick = []
    cleaners_overdue_kick = []

    for member in guild.members:
        if member.bot:
            continue

        member_roles = [r.name for r in member.roles]
        if any(role in EXEMPT_ROLES for role in member_roles if role in ["Major", "General"]):
            continue

        last_active = None

        for channel in guild.text_channels:
            try:
                async for msg in channel.history(limit=5000):
                    if msg.author == member:
                        if not last_active or msg.created_at > last_active:
                            last_active = msg.created_at
                        break
            except discord.Forbidden:
                continue

        if member.voice and member.voice.channel:
            # Only treat as active if joined voice within last 24h
            if member.voice.self_deaf is False:  # Optional: check if they're actually listening
                voice_active_threshold = now - timedelta(hours=24)
                if last_active is None or last_active < voice_active_threshold:
                    last_active = voice_active_threshold

        if not last_active:
            last_active = member.joined_at or datetime(1970, 1, 1, tzinfo=timezone.utc)

        if last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=timezone.utc)
            
        days_since_join = (now - member.joined_at).days if member.joined_at else 0
        if days_since_join < 180:
            continue  # Too new to consider for kick

        days_since = (now - last_active).days

        if CLEANER_ROLE_NAME in member_roles:
            kick_in_days = 180 - days_since
            if kick_in_days <= 0:
                cleaners_overdue_kick.append((member.display_name, abs(kick_in_days)))
            elif kick_in_days <= 14:
                cleaners_soon_kick.append((member.display_name, kick_in_days))
        else:
            cleaner_in_days = 90 - days_since
            if cleaner_in_days <= 14 and cleaner_in_days >= 0:
                nearing_inactive.append((member.display_name, cleaner_in_days))
            elif cleaner_in_days < 0:
                overdue_cleaners.append((member.display_name, abs(cleaner_in_days)))

    if not nearing_inactive and not cleaners_soon_kick and not cleaners_overdue_kick:
        await ctx.send("✅ All members are active or not near cleanup thresholds.")
        return

    desc = ""

    if nearing_inactive:
        desc += "**Members nearing inactivity (Cleaner role):**\n"
        for name, days_left in sorted(nearing_inactive, key=lambda x: x[1]):
            desc += f"• `{name}` — in `{days_left}` days\n"
    
    if overdue_cleaners:
        desc += "\n**Members overdue for Cleaner role:**\n"
        for name, overdue_days in sorted(overdue_cleaners, key=lambda x: x[1], reverse=True):
            desc += f"• `{name}` — overdue by `{overdue_days}` days\n"

    if cleaners_soon_kick:
        desc += "\n**Cleaners close to being kicked (≤14 days):**\n"
        for name, days_left in sorted(cleaners_soon_kick, key=lambda x: x[1]):
            desc += f"• `{name}` — kick in `{days_left}` days\n"

    if cleaners_overdue_kick:
        desc += "\n**Cleaners overdue for kick:**\n"
        for name, days_overdue in sorted(cleaners_overdue_kick, key=lambda x: x[1], reverse=True):
            desc += f"• `{name}` — kick overdue by `{days_overdue}` days\n"

    embed = create_embed(
        title="🕓 Inactivity Report",
        description=desc,
        color=discord.Color.blurple()
    )
    await ctx.send(embed=embed)


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
        if any(role in EXEMPT_ROLES for role in member_roles):
            continue

        # Skip recent joins (< 180 days)
        days_since_join = (now - member.joined_at).days if member.joined_at else 0
        if days_since_join < 180:
            continue

        # Determine last activity
        last_active = None
        for channel in guild.text_channels:
            try:
                async for msg in channel.history(limit=5000):
                    if msg.author == member:
                        if not last_active or msg.created_at > last_active:
                            last_active = msg.created_at
                        break
            except discord.Forbidden:
                continue

        if member.voice and member.voice.channel:
            # Only treat as active if joined voice within last 24h
            if member.voice.self_deaf is False:  # Optional: check if they're actually listening
                voice_active_threshold = now - timedelta(hours=24)
                if last_active is None or last_active < voice_active_threshold:
                    last_active = voice_active_threshold

        if not last_active:
            last_active = member.joined_at or datetime(1970, 1, 1, tzinfo=timezone.utc)

        if last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=timezone.utc)

        days_since_active = (now - last_active).days

        cleaner_role = discord.utils.get(guild.roles, name=CLEANER_ROLE_NAME)
        soldier_role = discord.utils.get(guild.roles, name=SOLDIER_ROLE_NAME)

        # ✅ Became active again
        if CLEANER_ROLE_NAME in member_roles and last_active >= inactive_cutoff:
            try:
                if cleaner_role:
                    await member.remove_roles(cleaner_role, reason="Active again")
                if warning_channel:
                    embed = create_embed(
                        title="Member active again ✅",
                        description=(
                            f"{member.mention} became active again. `Cleaner` role removed.\n"
                            f"<@&{GENERAL_ROLE_ID}> may want to restore previous roles."
                        ),
                        color=discord.Color.green()
                    )
                    await warning_channel.send(embed=embed)
                print(f"{member.name} became active again.")
            except discord.Forbidden:
                print(f"No permission to update roles for {member.name}")
            continue

        # 🚫 Kick after 180 days of inactivity
        if CLEANER_ROLE_NAME in member_roles and last_active < kick_cutoff:
            # Commented out for now:
            # try:
            #     await member.kick(reason="Inactive for more than 180 days")
            #     print(f"Kicked: {member.name}")
            #     if warning_channel:
            #         embed = create_embed(
            #             title="Member kicked for inactivity 🧹",
            #             description=f"{member.display_name} was kicked for 180+ days of inactivity.",
            #             color=discord.Color.red()
            #         )
            #         await warning_channel.send(embed=embed)
            # except discord.Forbidden:
            #     print(f"No permission to kick {member.name}")
            continue

        # 🧹 Mark as inactive if over 90 days and not yet a Cleaner
        if CLEANER_ROLE_NAME not in member_roles and last_active < inactive_cutoff:
            roles_to_remove = [
                r for r in member.roles
                if r.name not in EXEMPT_ROLES and r != guild.default_role
            ]
            try:
                if roles_to_remove:
                    await member.remove_roles(*roles_to_remove, reason="Marked inactive")

                if cleaner_role:
                    await member.add_roles(cleaner_role, reason="Inactive 90+ days")

                    original_roles_str = ", ".join([r.name for r in roles_to_remove]) or "None"
                    embed = create_embed(
                        title="Inactivity detected 🙁",
                        description=(
                            f"Attention {member.mention}, you have been marked as inactive and therefore "
                            f"degraded to the `Cleaner` role. 🙁🧹 Sorry, there is no kitchen service on this server. 😂\n"
                            f"Please become active to avoid removal. 🙏🏻\n\n"
                            f"For Admin's reference: Original roles before cleanup: `{original_roles_str}`."
                        )
                    )
                    if warning_channel:
                        await warning_channel.send(embed=embed)

                if soldier_role and soldier_role not in member.roles:
                    await member.add_roles(soldier_role, reason="Maintain Soldier role")

                print(f"Updated: {member.name}")
            except discord.Forbidden:
                print(f"No permission to update roles for {member.name}")

bot.run(TOKEN)
