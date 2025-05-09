import os
import discord
import csv
from discord.ext import tasks, commands
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from typing import Dict, Tuple
from io import StringIO

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID"))

CLEANER_ROLE_ID = 1225867465259618396
SOLDIER_ROLE_ID = 1109506946689671199
EXEMPT_ROLE_IDS = [1109510121454837822, 1269752542515040477]
WARNING_CHANNEL_ID = 1109096955252068384
GENERAL_ROLE_ID = 1269752542515040477  
STAFF_CHANNEL_ID = 1194194222702661632 

intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
cache_ready = False
cache_progress = 0  # 0 to 100

# Activity cache: member_id -> last_active datetime
activity_cache: Dict[int, datetime] = {}


def create_embed(title: str, description: str, color=discord.Color.orange()):
    return discord.Embed(title=title, description=description, color=color)


async def get_last_activity(member: discord.Member, guild: discord.Guild) -> datetime:
    """Scans all channels to determine the most recent message timestamp from the member."""
    now = datetime.now(timezone.utc)
    latest_msg_time = member.joined_at or datetime(1970, 1, 1, tzinfo=timezone.utc)

    for channel in guild.text_channels:
        if not channel.permissions_for(guild.me).read_messages:
            continue
        try:
            async for msg in channel.history(limit=5000, oldest_first=False):
                if msg.author.id == member.id:
                    if msg.created_at > latest_msg_time:
                        latest_msg_time = msg.created_at.replace(tzinfo=timezone.utc)
        except (discord.Forbidden, discord.HTTPException):
            continue

    return latest_msg_time


async def refresh_activity_cache(guild: discord.Guild):
    global cache_ready, cache_progress
    cache_ready = False
    cache_progress = 0
    activity_cache.clear()

    non_bot_members = [m for m in guild.members if not m.bot]
    total = len(non_bot_members)

    for index, member in enumerate(non_bot_members, start=1):
        last_active = await get_last_activity(member, guild)
        activity_cache[member.id] = last_active

        # Update percentage progress
        cache_progress = int((index / total) * 100)

    cache_progress = 100
    cache_ready = True


@bot.event
async def on_ready():
    print(f"Bot connected as {bot.user}")
    guild = bot.get_guild(GUILD_ID)
    if guild:
        print("Refreshing activity cache immediately...")
        await refresh_activity_cache(guild)  # 👈 Initial cache fill
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
        
        
@bot.event
async def on_message(message):
    if message.author.bot:
        return  # Ignore bots

    if cache_ready:
        # Only update cache if ready
        activity_cache[message.author.id] = datetime.now(timezone.utc)

    await bot.process_commands(message)  # Always allow commands to run
        
        
@bot.command(name="commands", help="Displays a list of all available bot commands (General role only).")
async def list_commands(ctx):
    if not any(role.id == GENERAL_ROLE_ID for role in ctx.author.roles):
        await ctx.send("❌ You do not have permission to use this command.")
        return

    if not cache_ready:
        await ctx.send(f"⏳ Please wait, I'm still scanning activity. Status: {cache_progress}%. Try again in a few minutes.")
        return

    embed = discord.Embed(
        title="Available Bot Commands",
        color=discord.Color.blue()
    )

    for command in bot.commands:
        if command.hidden:
            continue
        description = command.help or "No description available."
        embed.add_field(name=f"!{command.name}", value=description, inline=False)

    await ctx.send(embed=embed)


@bot.command(help="Lists all channels the bot cannot read (due to missing permissions).")
async def unreadable_channels(ctx):
    if not any(role.id == GENERAL_ROLE_ID for role in ctx.author.roles):
        await ctx.send("❌ You do not have permission to use this command.")
        return

    if not cache_ready:
        await ctx.send(f"⏳ Please wait, I'm still scanning activity. Status: {cache_progress}%. Try again in a few minutes.")
        return

    guild = bot.get_guild(GUILD_ID)
    unreadable = [
        channel.name for channel in guild.text_channels
        if not channel.permissions_for(guild.me).read_messages
    ]

    if not unreadable:
        await ctx.send("✅ Bot can read all text channels.")
    else:
        await ctx.send(
            "⚠️ Cannot read these channels:\n" + "\n".join(f"• #{name}" for name in unreadable)
        )


@bot.command(help="Shows the last known activity date and server join date for a specific member.")
async def lastactive(ctx, member: discord.Member):
    if not any(role.id == GENERAL_ROLE_ID for role in ctx.author.roles):
        await ctx.send("❌ You do not have permission to use this command.")
        return

    if not cache_ready:
        await ctx.send(f"⏳ Please wait, I'm still scanning activity. Status: {cache_progress}%. Try again in a few minutes.")
        return

    last_active = activity_cache.get(member.id)
    if not last_active:
        await ctx.send("⚠️ Activity data not yet available for this member. Try again later.")
        return

    last_active_str = last_active.strftime('%Y-%m-%d %H:%M:%S UTC')
    days_ago = (datetime.now(timezone.utc) - last_active).days
    join_date = member.joined_at.strftime('%Y-%m-%d %H:%M:%S UTC') if member.joined_at else "Unknown"

    embed = discord.Embed(
        title=f"🕵️ Last Activity for {member.display_name}",
        color=discord.Color.orange()
    )
    embed.add_field(name="📅 Joined Server", value=join_date, inline=False)
    embed.add_field(name="📊 Last Activity", value=f"{last_active_str} ({days_ago} days ago)", inline=False)

    await ctx.send(embed=embed)
    
    
@bot.command(help="Exports the activity cache as a CSV file, including inactive members and their roles.")
async def exportactivity(ctx):
    if not any(role.id == GENERAL_ROLE_ID for role in ctx.author.roles):
        await ctx.send("❌ You do not have permission to use this command.")
        return

    if not cache_ready:
        await ctx.send(f"⏳ Please wait, I'm still scanning activity. Status: {cache_progress}%. Try again in a few minutes.")
        return

    now = datetime.now(timezone.utc)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["User ID", "Display Name", "Last Active (UTC)", "Days Ago", "Joined At (UTC)", "Roles"])

    for member in ctx.guild.members:
        if member.bot:
            continue  # Skip bots

        user_id = member.id
        last_seen = activity_cache.get(user_id)
        joined_at = member.joined_at.strftime('%Y-%m-%d %H:%M:%S') if member.joined_at else "Unknown"
        roles = "; ".join(role.name for role in member.roles if role.name != "@everyone")

        if last_seen:
            days_ago = (now - last_seen).days
            last_seen_str = last_seen.strftime('%Y-%m-%d %H:%M:%S')
            days_ago_str = str(days_ago)
        else:
            last_seen_str = "Never"
            days_ago_str = "Not in cache"

        writer.writerow([
            str(user_id),
            member.display_name,
            last_seen_str,
            days_ago_str,
            joined_at,
            roles
        ])

    output.seek(0)
    csv_file = discord.File(fp=output, filename="activity_cache_full.csv")
    await ctx.send("📁 Full activity cache including inactive members:", file=csv_file)


@bot.command(help="Displays an inactivity report. Add 'clean' to only show members near Cleaner or kick thresholds.")
async def inactivity_report(ctx, *args):
    if not any(role.id == GENERAL_ROLE_ID for role in ctx.author.roles):
        await ctx.send("❌ You do not have permission to use this command.")
        return

    if not cache_ready:
        await ctx.send(f"⏳ Please wait, I'm still scanning activity. Status: {cache_progress}%. Try again in a few minutes.")
        return

    minimal = "clean" in args
    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        await ctx.send("⚠️ Guild not found. Please try again later.")
        return

    now = datetime.now(timezone.utc)

    nearing_inactive = []
    overdue_cleaners = []
    cleaners_soon_kick = []
    cleaners_overdue_kick = []
    cleaner_list = []
    active_members = []
    uncached_members = []

    for member in guild.members:
        if member.bot:
            continue

        last_active = activity_cache.get(member.id)
        joined_at = member.joined_at or now
        days_since_join = (now - joined_at).days
        is_cleaner = any(role.id == CLEANER_ROLE_ID for role in member.roles)
        is_exempt = any(role.id in EXEMPT_ROLE_IDS for role in member.roles)

        if is_exempt:
            continue

        # Handle members who never became active
        if not last_active:
            if days_since_join >= 90 and not is_cleaner:
                overdue_cleaners.append((member.display_name, f"never active, joined {days_since_join}d ago"))
            elif not minimal:
                uncached_members.append(member.display_name)
            continue

        days_since = (now - last_active).days

        if is_cleaner:
            kick_in_days = 180 - days_since
            if kick_in_days <= 0:
                cleaners_overdue_kick.append((member.display_name, abs(kick_in_days)))
            elif kick_in_days <= 14:
                cleaners_soon_kick.append((member.display_name, kick_in_days))
            else:
                cleaner_list.append((member.display_name, kick_in_days))
        else:
            cleaner_in_days = 90 - days_since
            if cleaner_in_days < 0:
                overdue_cleaners.append((member.display_name, abs(cleaner_in_days)))
            elif cleaner_in_days <= 14:
                nearing_inactive.append((member.display_name, cleaner_in_days))
            else:
                if not minimal:
                    active_members.append((member.display_name, f"{days_since} days ago"))

    # Sort all lists
    nearing_inactive.sort(key=lambda x: x[1])
    overdue_cleaners.sort(key=lambda x: int(str(x[1]).split()[0]) if isinstance(x[1], str) else x[1])
    cleaners_soon_kick.sort(key=lambda x: x[1])
    cleaners_overdue_kick.sort(key=lambda x: x[1])
    cleaner_list.sort(key=lambda x: x[1])
    active_members.sort(key=lambda x: int(x[1].split()[0]) if x[1] != "Unknown" else 999)

    # Compose embed description
    desc = ""

    def add_section(title, members):
        nonlocal desc
        if members:
            desc += f"\n\n**{title} ({len(members)}):**\n"
            desc += "\n".join(f"• `{name}` — {info}" for name, info in members)

    add_section("✅ Active Members", active_members)
    add_section("⚠️ Members nearing inactivity (Cleaner role)", nearing_inactive)
    add_section("🧹 Cleaners (not yet close to kick)", cleaner_list)
    add_section("⏳ Members overdue for Cleaner role", overdue_cleaners)
    add_section("❗ Cleaners close to being kicked (≤14 days)", cleaners_soon_kick)
    add_section("🔥 Cleaners overdue for kick", cleaners_overdue_kick)

    if uncached_members and not minimal:
        desc += f"\n\n**⚠️ Members not yet analyzed (no messages seen) ({len(uncached_members)}):**\n"
        desc += "\n".join(f"• `{name}`" for name in uncached_members)

    # Totals
    total_count = len([
        member for member in guild.members
        if not member.bot and not any(role.id in EXEMPT_ROLE_IDS for role in member.roles)
    ])

    listed_count = (
        len(active_members)
        + len(nearing_inactive)
        + len(cleaner_list)
        + len(overdue_cleaners)
        + len(cleaners_soon_kick)
        + len(cleaners_overdue_kick)
        + (len(uncached_members) if not minimal else 0)
    )

    desc += f"\n\n**👥 Members displayed: `{listed_count}` / Analyzed (excluding bots & exempt): `{total_count}`**"

    if not desc.strip():
        desc = "✅ All members are active or not near cleanup thresholds."

    embed = create_embed("🕓 Inactivity Report", desc.strip(), discord.Color.blurple())
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
    warning_channel = guild.get_channel(WARNING_CHANNEL_ID)

    print(f"Activity cache before refresh: {len(activity_cache)}")  # Debug log
    await refresh_activity_cache(guild)
    print(f"Activity cache after refresh: {len(activity_cache)}")  # Debug log

    for member in guild.members:
        if member.bot or any(r.id in EXEMPT_ROLE_IDS for r in member.roles):
            continue

        days_since_join = (now - (member.joined_at or now)).days
        if days_since_join < 180:
            continue

        last_active = activity_cache.get(member.id)
        role_names = [r.name for r in member.roles]

        cleaner_role = guild.get_role(CLEANER_ROLE_ID)
        soldier_role = guild.get_role(SOLDIER_ROLE_ID)

        # 🧹 Handle members who never became active
        if last_active is None:
            if CLEANER_ROLE_NAME not in role_names and days_since_join >= 90:
                roles_to_remove = [
                    r for r in member.roles
                    if r.name not in EXEMPT_ROLES and r != guild.default_role
                ]
                try:
                    if roles_to_remove:
                        await member.remove_roles(*roles_to_remove, reason="Marked inactive (never active)")

                    if cleaner_role:
                        await member.add_roles(cleaner_role, reason="Inactive (never active)")
                        if warning_channel:
                            await warning_channel.send(embed=create_embed(
                                "Inactivity detected 🙁",
                                f"Attention {member.mention}, you have been marked as inactive and therefore "
                                f"degraded to the `Cleaner` role. 🙁🧹 Sorry, there is no kitchen service on this server. 😂\n"
                                f"Please become active to avoid removal. 🙏🏻\n\n"
                                f"For Admin's reference: Original roles before cleanup: "
                                f"`{', '.join([r.name for r in roles_to_remove]) or 'None'}`."
                            ))

                    if soldier_role and soldier_role not in member.roles:
                        await member.add_roles(soldier_role, reason="Maintain Soldier role")

                except discord.Forbidden:
                    print(f"No permission to update roles for {member.name}")
            continue

        days_since = (now - last_active).days

        # ✅ Became active again
        if CLEANER_ROLE_NAME in role_names and last_active >= inactive_cutoff:
            try:
                await member.remove_roles(cleaner_role, reason="Active again")
                if warning_channel:
                    await warning_channel.send(embed=create_embed(
                        "Member active again ✅",
                        f"{member.mention} became active again. `Cleaner` role removed.\n"
                        f"<@&{GENERAL_ROLE_ID}> may want to restore previous roles.",
                        discord.Color.green()
                    ))
            except discord.Forbidden:
                print(f"No permission to update roles for {member.name}")
            continue

        # 🚫 Kick after 180 days of inactivity (verification step)
        if CLEANER_ROLE_NAME in role_names and last_active < kick_cutoff:
            print(f"Preparing to flag {member.name} for kick verification")  # Debug log
            staff_channel = bot.get_channel(STAFF_CHANNEL_ID)
            if staff_channel:
                embed = create_embed(
                    title="⚠️ Kick candidate: Inactive >180 days",
                    description=(
                        f"{member.mention} has been inactive for over **{(now - last_active).days} days** "
                        f"and still has the `Cleaner` role.\n"
                        f"Joined: <t:{int(member.joined_at.timestamp())}:D>\n"
                        f"Last active: <t:{int(last_active.timestamp())}:R>\n\n"
                        f"Please verify before enabling the auto-kick."
                    ),
                    color=discord.Color.orange()
                )
                embed.set_footer(text="Auto-kick is currently disabled for safety.")
                await staff_channel.send(embed=embed)
            continue

        # 🧹 Mark as inactive if over 90 days and not yet a Cleaner
        if CLEANER_ROLE_NAME not in role_names and last_active < inactive_cutoff:
            roles_to_remove = [
                r for r in member.roles
                if r.name not in EXEMPT_ROLES and r != guild.default_role
            ]
            try:
                if roles_to_remove:
                    await member.remove_roles(*roles_to_remove, reason="Marked inactive")

                if cleaner_role:
                    await member.add_roles(cleaner_role, reason="Inactive 90+ days")
                    if warning_channel:
                        await warning_channel.send(embed=create_embed(
                            "Inactivity detected 🙁",
                            f"Attention {member.mention}, you have been marked as inactive and therefore "
                            f"degraded to the `Cleaner` role. 🙁🧹 Sorry, there is no kitchen service on this server. 😂\n"
                            f"Please become active to avoid removal. 🙏🏻\n\n"
                            f"For Admin's reference: Original roles before cleanup: "
                            f"`{', '.join([r.name for r in roles_to_remove]) or 'None'}`."
                        ))

                if soldier_role and soldier_role not in member.roles:
                    await member.add_roles(soldier_role, reason="Maintain Soldier role")

            except discord.Forbidden:
                print(f"No permission to update roles for {member.name}")
                
bot.run(TOKEN)
