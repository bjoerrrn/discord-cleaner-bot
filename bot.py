import os
import discord
import csv
import asyncio
from discord.ext import tasks, commands
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from typing import Dict, Tuple
from io import StringIO
from asyncio import Lock

inactivity_check_lock = Lock()
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID"))

# IDs
CLEANER_ROLE_ID = 1225867465259618396
SOLDIER_ROLE_ID = 1109506946689671199
EXEMPT_ROLE_IDS = [1109510121454837822, 1269752542515040477]
WARNING_CHANNEL_ID = 1109096955252068384
GENERAL_ROLE_ID = 1269752542515040477  
STAFF_CHANNEL_ID = 1194194222702661632 

# Constants
INACTIVITY_THRESHOLD = 90
KICK_THRESHOLD = 180
MAX_MESSAGE_LOOKBACK = 5000

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
    latest_msg_time = member.joined_at or datetime(1970, 1, 1, tzinfo=timezone.utc)

    for channel in guild.text_channels:
        if not channel.permissions_for(guild.me).read_messages:
            continue
        if channel.last_message_id is None:
            continue
        try:
            async for msg in channel.history(limit=MAX_MESSAGE_LOOKBACK):
                if msg.author.id == member.id:
                    latest_msg_time = max(latest_msg_time, msg.created_at)
        except asyncio.TimeoutError:
            print(f"⏰ Timeout fetching history in #{channel.name} (ID: {channel.id})")
        except (discord.Forbidden, discord.HTTPException) as e:
            print(f"⚠️ Error reading #{channel.name} (ID: {channel.id}): {e}")
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
        print(f"{member.display_name} last active: {last_active.isoformat()}")
        
        activity_cache[member.id] = last_active

        # Update percentage progress
        cache_progress = int((index / total) * 100)

    cache_progress = 100
    cache_ready = True
    
    
def has_role(member, role_id):
    return any(role.id == role_id for role in member.roles)


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
async def on_message_edit(before, after):
    if after.author.bot:
        return  # Ignore bots

    if cache_ready:
        activity_cache[after.author.id] = datetime.now(timezone.utc)
        
        
@bot.event
async def on_message(message):
    if message.author.bot:
        return  # Ignore bots

    if cache_ready:
        # Only update cache if ready
        activity_cache[message.author.id] = datetime.now(timezone.utc)

    await bot.process_commands(message)  # Always allow commands to run
        
        
@bot.command(name="commands", help="Displays a list of all available bot commands (General role only).")
@commands.has_role(GENERAL_ROLE_ID)
async def list_commands(ctx):
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
@commands.has_role(GENERAL_ROLE_ID)
async def unreadable_channels(ctx):
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
@commands.has_role(GENERAL_ROLE_ID)
async def lastactive(ctx, member: discord.Member):
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
@commands.has_role(GENERAL_ROLE_ID)
async def exportactivity(ctx):
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
@commands.has_role(GENERAL_ROLE_ID)
async def inactivity_report(ctx, *args):
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
            if days_since_join >= INACTIVITY_THRESHOLD and not is_cleaner:
                overdue_cleaners.append((member.display_name, f"{days_since_join} days ago joined, never active"))
            elif not minimal:
                uncached_members.append(member.display_name)
            continue

        days_since = (now - last_active).days

        if is_cleaner:
            kick_in_days = KICK_THRESHOLD - days_since
            if kick_in_days <= 0:
                cleaners_overdue_kick.append((member.display_name, f"{abs(kick_in_days)} days overdue"))
            elif kick_in_days <= 14:
                cleaners_soon_kick.append((member.display_name, f"{kick_in_days} days ahead"))
            else:
                cleaner_list.append((member.display_name, f"{kick_in_days} days ahead"))
        else:
            cleaner_in_days = INACTIVITY_THRESHOLD - days_since
            if cleaner_in_days < 0:
                overdue_cleaners.append((member.display_name, f"{abs(cleaner_in_days)} days overdue"))
            elif cleaner_in_days <= 14:
                nearing_inactive.append((member.display_name, f"{cleaner_in_days} days ahead"))
            else:
                if not minimal:
                    active_members.append((member.display_name, f"{days_since} days ago"))

    # Sort all lists
    nearing_inactive.sort(key=lambda x: int(x[1].split()[0]))
    overdue_cleaners.sort(key=lambda x: int(x[1].split()[0]))
    cleaners_soon_kick.sort(key=lambda x: int(x[1].split()[0]))
    cleaners_overdue_kick.sort(key=lambda x: int(x[1].split()[0]))
    cleaner_list.sort(key=lambda x: int(x[1].split()[0]))
    active_members.sort(key=lambda x: int(x[1].split()[0]))

    # Compose embed description
    desc = ""

    def add_section(title, members):
        nonlocal desc
        if members:
            desc += f"\n\n**{title} ({len(members)}):**\n"
            desc += "\n".join(f"• `{name}` — {info}" for name, info in members)

    add_section("✅ Active Members", active_members)
    add_section("⚠️ Members nearing inactivity (Cleaner role)", nearing_inactive)
    add_section("⏳ Members overdue for Cleaner role", overdue_cleaners)
    add_section("🧹 Cleaners (not yet close to kick)", cleaner_list)
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
    
    
async def check_inactive_members_function():
    print("Waiting for inactivity_check_lock...")
    async with inactivity_check_lock:
        print("Acquired inactivity_check_lock, starting check...")
        
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            print("Guild not found.")
            return
    
        print(f"Activity cache before refresh: {len(activity_cache)}")  # Debug log
        await refresh_activity_cache(guild)
        print(f"Activity cache after refresh: {len(activity_cache)}")  # Debug log
    
        now = datetime.now(timezone.utc)
        inactive_cutoff = now - timedelta(days=INACTIVITY_THRESHOLD)
        kick_cutoff = now - timedelta(days=KICK_THRESHOLD)
        warning_channel = guild.get_channel(WARNING_CHANNEL_ID)
    
        for member in guild.members:
            if member.bot or any(r.id in EXEMPT_ROLE_IDS for r in member.roles):
                print(f"Skipping {member.display_name} ({member.id}): Bot or exempt role")
                continue
        
            last_active = activity_cache.get(member.id)
            days_since_join = (now - (member.joined_at or now)).days
        
            if days_since_join < KICK_THRESHOLD and (last_active is None or (now - last_active).days < INACTIVITY_THRESHOLD):
                print(f"Skipping {member.display_name} ({member.id}): Joined {days_since_join} days ago or active in last {INACTIVITY_THRESHOLD} days")
                continue
                
            cleaner_role = guild.get_role(CLEANER_ROLE_ID)
            soldier_role = guild.get_role(SOLDIER_ROLE_ID)
    
            # 🧹 Handle members who never became active
            if last_active is None:
                print(f"{member.display_name} ({member.id}) has never been active, joined {days_since_join} days ago")
                if cleaner_role not in member.roles and days_since_join >= INACTIVITY_THRESHOLD:
                    roles_to_remove = [
                        r for r in member.roles
                        if r.id not in EXEMPT_ROLE_IDS and r != guild.default_role
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
            if cleaner_role in member.roles and last_active >= inactive_cutoff:
                print(f"{member.display_name} ({member.id}) is Cleaner but became active again")
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
    
            # 🚫 Kick after KICK_THRESHOLD days of inactivity (verification step)
            if cleaner_role in member.roles and last_active < kick_cutoff:
                print(f"{member.display_name} ({member.id}) is overdue for kick ({(now - last_active).days} days inactive)")
                try:
                    await member.kick(reason="Inactive for more than {KICK_THRESHOLD} days")
                    print(f"Kicked: {member.name}")
                    if warning_channel:
                        embed = create_embed(
                            title="Member kicked for inactivity 🧹",
                            description=f"{member.display_name} was kicked for {KICK_THRESHOLD}+ days of inactivity.",
                            color=discord.Color.red()
                        )
                        await warning_channel.send(embed=embed)
                except discord.Forbidden:
                    print(f"No permission to kick {member.name}")
                
                # staff_channel = bot.get_channel(STAFF_CHANNEL_ID)
                # if staff_channel:
                #     embed = create_embed(
                #         title="⚠️ Kick candidate: Inactive >KICK_THRESHOLD days",
                #         description=(
                #             f"{member.mention} has been inactive for over **{(now - last_active).days} days** "
                #             f"and still has the `Cleaner` role.\n"
                #             f"Joined: <t:{int(member.joined_at.timestamp())}:D>\n"
                #             f"Last active: <t:{int(last_active.timestamp())}:R>\n\n"
                #             f"Please verify before enabling the auto-kick."
                #         ),
                #         color=discord.Color.orange()
                #     )
                #     embed.set_footer(text="Auto-kick is currently disabled for safety.")
                #     await staff_channel.send(embed=embed)
                continue
    
            # 🧹 Mark as inactive if over INACTIVITY_THRESHOLD days and not yet a Cleaner
            if cleaner_role not in member.roles and last_active < inactive_cutoff:
                print(f"{member.display_name} ({member.id}) is overdue for Cleaner role ({(now - last_active).days} days inactive)")
                roles_to_remove = [
                    r for r in member.roles
                    if r.id not in EXEMPT_ROLE_IDS and r != guild.default_role
                ]
                try:
                    if roles_to_remove:
                        await member.remove_roles(*roles_to_remove, reason="Marked inactive")
    
                    if cleaner_role:
                        await member.add_roles(cleaner_role, reason="Inactive {INACTIVITY_THRESHOLD}+ days")
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


@bot.command(name="run_inactivity_check", aliases=["check_inactive", "manual_inactive_check"], help="Runs the inactivity check manually.")
@commands.has_role(GENERAL_ROLE_ID)
async def run_inactivity_check(ctx):
    if inactivity_check_lock.locked():
        await ctx.send("⚠️ Inactivity check is already running. Please wait.")
        return

    await ctx.send("✅ Running inactivity check...")
    try:
        await check_inactive_members_function()
    except Exception as e:
        print(f"❌ Inactivity check failed: {e}")
        await ctx.send(f"❌ Inactivity check failed: {e}")
    await ctx.send("✅ Inactivity check completed.")


@bot.command(name="next_check", help="Shows the next scheduled run of the inactivity check.")
@commands.has_role(GENERAL_ROLE_ID)
async def next_check(ctx):
    next_run = check_inactive_members_task.next_iteration
    if next_run:
        await ctx.send(
            embed=discord.Embed(
                title="🕒 Next Inactivity Check",
                description=f"The next check is scheduled for: <t:{int(next_run.timestamp())}:F>",
                color=discord.Color.green()
            )
        )
    else:
        await ctx.send(
            embed=discord.Embed(
                title="⚠️ Task Not Running",
                description="The background task has not been started or the next run time is not available.",
                color=discord.Color.red()
            )
        )


@tasks.loop(hours=24)
async def check_inactive_members_task():
    await check_inactive_members_function()


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    if not check_inactive_members_task.is_running():
        check_inactive_members_task.start()


bot.run(TOKEN)
