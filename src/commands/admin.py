"""
Admin Command Module for Sir Tim the Timely

Implements admin commands for managing the bot and its settings.
"""

import logging
from datetime import datetime, timezone
from typing import Set

import hikari
import arc
from hikari.errors import NotFoundError, BadRequestError

from ..database import DatabaseManager
from ..scraper import MITDeadlineScraper
from ..reminder_system import ReminderSystem
from ..gemini_chat_handler import GeminiChatHandler

logger = logging.getLogger("sir_tim.commands.admin")

# Create a plugin for admin commands
plugin = arc.GatewayPlugin("admin")

# Admin role whitelist - stores role IDs that can use admin commands
admin_role_whitelist: Set[int] = set()

def is_admin_authorized(member: hikari.Member) -> bool:
    """Check if a member is authorized to use admin commands."""
    if not member:
        return False
    
    # Check if user has administrator permissions
    if member.permissions.ADMINISTRATOR:
        return True
    
    # Check if user has any whitelisted roles
    member_role_ids = {role.id for role in member.get_roles()}
    return bool(admin_role_whitelist.intersection(member_role_ids))

# Define admin command group
admin = plugin.include_slash_group("admin", "Administrative commands for bot management")

from ..gemini_chat_handler import GeminiChatHandler
@admin.include
@arc.slash_subcommand("setchat", "Set current channel for Tim to chat in (Admin only)")
async def admin_set_chat_channel(ctx: arc.GatewayContext) -> None:
    """Set the current channel for Tim to respond in (admin only)."""
    if not is_admin_authorized(ctx.member):
        await ctx.respond("This command can only be used by server administrators or whitelisted admin roles.", flags=hikari.MessageFlag.EPHEMERAL)
        return
    if not ctx.guild_id:
        await ctx.respond("This command can only be used in a server.", flags=hikari.MessageFlag.EPHEMERAL)
        return
    try:
        llm_handler = ctx.client.get_type_dependency(GeminiChatHandler)
        await llm_handler.set_chat_channel(ctx.guild_id, ctx.channel_id)
        embed = hikari.Embed(
            title="✅ Chat Channel Set",
            description="Tim will now randomly respond in this channel with friendly and helpful wisdom.",
            color=0x00FF00
        )
        embed.add_field(
            name="How it works",
            value=(
                "• Tim responds randomly (~70% chance)\n"
                "• Higher chance if mentioned or when asking questions\n"
                "• Has a short cooldown to prevent spam\n"
                "• Friendly, wise, and genuinely helpful"
            ),
            inline=False
        )
        embed.add_field(
            name="Tips",
            value=(
                "• Mention Tim to get his attention\n"
                "• Ask about deadlines, stress, or MIT stuff\n"
                "• He's friendly and offers practical advice\n"
                "• Use `/admin removechat` to disable"
            ),
            inline=False
        )
        await ctx.respond(embed=embed)
    except Exception as e:
        logger.error(f"Error setting chat channel: {e}")
        await ctx.respond("Failed to set chat channel. Please try again.", flags=hikari.MessageFlag.EPHEMERAL)

# Remove chat channel admin command
@admin.include
@arc.slash_subcommand("removechat", "Remove Tim's chat functionality from this server (Admin only)")
async def admin_remove_chat_channel(ctx: arc.GatewayContext) -> None:
    """Remove Tim's chat functionality from this server (admin only)."""
    if not is_admin_authorized(ctx.member):
        await ctx.respond("This command can only be used by server administrators or whitelisted admin roles.", flags=hikari.MessageFlag.EPHEMERAL)
        return
    if not ctx.guild_id:
        await ctx.respond("This command can only be used in a server.", flags=hikari.MessageFlag.EPHEMERAL)
        return
    try:
        llm_handler = ctx.client.get_type_dependency(GeminiChatHandler)
        await llm_handler.remove_chat_channel(ctx.guild_id)
        embed = hikari.Embed(
            title="❌ Chat Disabled",
            description="Tim's chat functionality has been disabled for this server.",
            color=0xFF0000
        )
        embed.add_field(
            name="How to re-enable",
            value="Use `/admin setchat` in any channel to re-enable Tim's chat responses.",
            inline=False
        )
        await ctx.respond(embed=embed)
    except Exception as e:
        logger.error(f"Error removing chat channel: {e}")
        await ctx.respond("Failed to remove chat functionality. Please try again.", flags=hikari.MessageFlag.EPHEMERAL)


@admin.include
@arc.slash_subcommand("addrole", "Add a role to the admin whitelist")
async def add_admin_role(
    ctx: arc.GatewayContext,
    role: arc.Option[hikari.Role, arc.RoleParams("Role to add to admin whitelist")]
) -> None:
    """Add a role to the admin command whitelist."""
    # Check authorization
    if not is_admin_authorized(ctx.member):
        await ctx.respond("❌ You don't have permission to use admin commands.", flags=hikari.MessageFlag.EPHEMERAL)
        return
        
    # Only actual administrators can modify the whitelist
    if not ctx.member or not ctx.member.permissions.ADMINISTRATOR:
        await ctx.respond("Only server administrators can modify the admin role whitelist.", flags=hikari.MessageFlag.EPHEMERAL)
        return
    
    admin_role_whitelist.add(role.id)
    
    embed = hikari.Embed(
        title="✅ Admin Role Added",
        description=f"Role {role.mention} has been added to the admin whitelist.",
        color=0x00FF00,
        timestamp=datetime.now(timezone.utc)
    )
    
    embed.add_field(
        name="Permissions Granted",
        value="Members with this role can now use all `/admin` commands.",
        inline=False
    )
    
    embed.set_footer(text="Sir Tim the Timely • Admin Panel")
    await ctx.respond(embed=embed, flags=hikari.MessageFlag.EPHEMERAL)

@admin.include
@arc.slash_subcommand("removerole", "Remove a role from the admin whitelist")
async def remove_admin_role(
    ctx: arc.GatewayContext,
    role: arc.Option[hikari.Role, arc.RoleParams("Role to remove from admin whitelist")]
) -> None:
    """Remove a role from the admin command whitelist."""
    # Check authorization
    if not is_admin_authorized(ctx.member):
        await ctx.respond("❌ You don't have permission to use admin commands.", flags=hikari.MessageFlag.EPHEMERAL)
        return
        
    # Only actual administrators can modify the whitelist
    if not ctx.member or not ctx.member.permissions.ADMINISTRATOR:
        await ctx.respond("Only server administrators can modify the admin role whitelist.", flags=hikari.MessageFlag.EPHEMERAL)
        return
    
    if role.id in admin_role_whitelist:
        admin_role_whitelist.remove(role.id)
        
        embed = hikari.Embed(
            title="✅ Admin Role Removed",
            description=f"Role {role.mention} has been removed from the admin whitelist.",
            color=0xFF9900,
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(
            name="Permissions Revoked",
            value="Members with this role can no longer use `/admin` commands.",
            inline=False
        )
        
        embed.set_footer(text="Sir Tim the Timely • Admin Panel")
        await ctx.respond(embed=embed, flags=hikari.MessageFlag.EPHEMERAL)
    else:
        await ctx.respond(f"Role {role.mention} is not in the admin whitelist.", flags=hikari.MessageFlag.EPHEMERAL)

@admin.include
@arc.slash_subcommand("listroles", "List all roles in the admin whitelist")
async def list_admin_roles(ctx: arc.GatewayContext) -> None:
    """List all roles in the admin command whitelist."""
    # Check authorization
    if not is_admin_authorized(ctx.member):
        await ctx.respond("❌ You don't have permission to use admin commands.", flags=hikari.MessageFlag.EPHEMERAL)
        return
        
    if not admin_role_whitelist:
        embed = hikari.Embed(
            title="📋 Admin Role Whitelist",
            description="No roles are currently whitelisted for admin commands.",
            color=0x4285F4,
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(
            name="Default Access",
            value="Only users with Administrator permissions can use admin commands.",
            inline=False
        )
    else:
        role_mentions = []
        for role_id in admin_role_whitelist:
            try:
                role = ctx.get_guild().get_role(role_id)
                if role:
                    role_mentions.append(role.mention)
                else:
                    role_mentions.append(f"<@&{role_id}> (role not found)")
            except Exception:
                role_mentions.append(f"<@&{role_id}> (error)")
        
        embed = hikari.Embed(
            title="📋 Admin Role Whitelist",
            description="Roles that can use admin commands:",
            color=0x4285F4,
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(
            name="Whitelisted Roles",
            value="\n".join(f"• {role}" for role in role_mentions),
            inline=False
        )
        
        embed.add_field(
            name="Note",
            value="Users with Administrator permissions always have access.",
            inline=False
        )
    
    embed.set_footer(text="Sir Tim the Timely • Admin Panel")
    await ctx.respond(embed=embed, flags=hikari.MessageFlag.EPHEMERAL)

@admin.include
@arc.slash_subcommand("scrape", "Manually trigger deadline scraping")
async def scrape_deadlines(ctx: arc.GatewayContext) -> None:
    """Manually trigger deadline scraping from MIT website."""
    
    scraper = ctx.client.get_type_dependency(MITDeadlineScraper)
    
    await ctx.defer()
    
    try:
        await ctx.respond("Starting deadline scraping from MIT website...", flags=hikari.MessageFlag.EPHEMERAL)
        
        # Perform scraping
        deadlines = await scraper.scrape_deadlines()
        
        # Send result
        await ctx.respond(f"✅ Successfully scraped {len(deadlines)} deadlines from the MIT website!", flags=hikari.MessageFlag.EPHEMERAL)
        
    except Exception as e:
        logger.error(f"Error during manual scraping: {e}")
        await ctx.respond(f"❌ Error scraping deadlines: {str(e)}", flags=hikari.MessageFlag.EPHEMERAL)

@admin.include
@arc.slash_subcommand("reminderchannel", "Set the channel for daily reminders")
async def set_reminder_channel(ctx: arc.GatewayContext) -> None:
    """Set the current channel for daily reminders."""
    
    reminder_system = ctx.client.get_type_dependency(ReminderSystem)
    
    try:
        if ctx.guild_id is None:
            await ctx.respond("This command can only be used in a server.")
            return
            
        await reminder_system.set_reminder_channel(ctx.guild_id, ctx.channel_id)
        
        await ctx.respond("✅ This channel has been set as the reminder channel.", flags=hikari.MessageFlag.EPHEMERAL)
        
    except Exception as e:
        logger.error(f"Error setting reminder channel: {e}")
        await ctx.respond(f"❌ Error setting reminder channel: {str(e)}", flags=hikari.MessageFlag.EPHEMERAL)

@admin.include
@arc.slash_subcommand("adddeadline", "Add a custom deadline")
async def add_deadline(
    ctx: arc.GatewayContext,
    title: arc.Option[str, arc.StrParams("Title of the deadline")],
    description: arc.Option[str, arc.StrParams("Description of the deadline")],
    due_date: arc.Option[str, arc.StrParams("Due date (YYYY-MM-DD HH:MM format)")],
    category: arc.Option[str, arc.StrParams("Category for the deadline", choices={
        "General": "General",
        "Medical": "Medical", 
        "Academic": "Academic",
        "Housing": "Housing",
        "Financial": "Financial",
        "Orientation": "Orientation",
        "Administrative": "Administrative",
        "Registration": "Registration"
    })] = "General",
    is_critical: arc.Option[bool, arc.BoolParams("Is this a critical deadline?")] = False
) -> None:
    """Add a custom deadline to the database."""
    db_manager = ctx.client.get_type_dependency(DatabaseManager)
    
    try:
        # Parse the due date
        try:
            naive_due_date = datetime.strptime(due_date, "%Y-%m-%d %H:%M")
            # Assume the input is in US/Eastern time (MIT timezone)
            from zoneinfo import ZoneInfo
            eastern = ZoneInfo("US/Eastern")
            local_due_date = naive_due_date.replace(tzinfo=eastern)
            # Convert to UTC for storage
            parsed_due_date = local_due_date.astimezone(timezone.utc)
        except ValueError:
            await ctx.respond("❌ Invalid date format. Please use YYYY-MM-DD HH:MM format (e.g., 2024-12-25 23:59)")
            return
        
        # Add the deadline
        deadline_id = await db_manager.add_deadline(
            raw_title=title,
            title=title,
            description=description,
            due_date=parsed_due_date,
            category=category,
            is_critical=is_critical
        )
        
        await ctx.respond(f"✅ Added custom deadline: **{title}** with ID: {deadline_id}", flags=hikari.MessageFlag.EPHEMERAL)
        
    except Exception as e:
        logger.error(f"Error adding custom deadline: {e}")
        await ctx.respond(f"❌ Error adding deadline: {str(e)}", flags=hikari.MessageFlag.EPHEMERAL)

@admin.include
@arc.slash_subcommand("testreminder", "Send a test reminder")
async def test_reminder(ctx: arc.GatewayContext) -> None:
    """Send a test reminder to the current channel."""
    reminder_system = ctx.client.get_type_dependency(ReminderSystem)
    
    await ctx.defer()
    
    try:
        result = await reminder_system.send_test_reminder(ctx.channel_id)
        
        if result:
            await ctx.respond("✅ Test reminder sent successfully!", flags=hikari.MessageFlag.EPHEMERAL)
        else:
            await ctx.respond("❌ Failed to send test reminder.", flags=hikari.MessageFlag.EPHEMERAL)
        
    except Exception as e:
        logger.error(f"Error sending test reminder: {e}")
        await ctx.respond(f"❌ Error: {str(e)}", flags=hikari.MessageFlag.EPHEMERAL)

@admin.include
@arc.slash_subcommand("testreminddm", "Test sending a DM reminder for a deadline to yourself immediately")
async def test_remind_dm(
    ctx: arc.GatewayContext,
    deadline_id: arc.Option[int, arc.IntParams("ID of the deadline to test DM for")]
) -> None:
    """Admin-only: Test sending a DM reminder for a deadline immediately."""
    # Check authorization
    if not is_admin_authorized(ctx.member):
        await ctx.respond("❌ You don't have permission to use admin commands.", flags=hikari.MessageFlag.EPHEMERAL)
        return

    db_manager = ctx.client.get_type_dependency(DatabaseManager)
    deadlines = await db_manager.get_deadlines()
    deadline = next((d for d in deadlines if d['id'] == deadline_id), None)

    if not deadline:
        await ctx.respond("❌ Deadline not found. Please check the ID and try again.", flags=hikari.MessageFlag.EPHEMERAL)
        return

    # Compose DM embed with 'in X days/hours' format
    title = deadline.get('title', 'Untitled')
    desc = deadline.get('description', '')
    category = deadline.get('category', 'General')
    due_date_raw = deadline.get('due_date')
    due_dt = None
    time_left_str = "Unknown"
    if due_date_raw:
        try:
            from datetime import datetime, timezone
            if isinstance(due_date_raw, str):
                due_dt = datetime.fromisoformat(due_date_raw.replace('Z', '+00:00'))
            else:
                due_dt = due_date_raw
            now = datetime.now(timezone.utc)
            delta = due_dt - now
            days = delta.days
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60
            if days > 0:
                time_left_str = f"in {days} day{'s' if days != 1 else ''}"
            elif hours > 0:
                time_left_str = f"in {hours} hour{'s' if hours != 1 else ''}"
            elif minutes > 0:
                time_left_str = f"in {minutes} minute{'s' if minutes != 1 else ''}"
            elif delta.total_seconds() > 0:
                time_left_str = "soon"
            else:
                time_left_str = "(already passed)"
        except Exception:
            pass

    # Format Discord timestamp markdown if possible
    timestamp_str = due_date_raw
    if due_dt:
        unix_ts = int(due_dt.timestamp())
        timestamp_str = f"<t:{unix_ts}:F> (<t:{unix_ts}:R>)"

    embed = hikari.Embed(
        title=f"⏰ Reminder: {title}",
        description=f"Category: {category}\nDue: {timestamp_str}\n\n{desc}",
        color=0x00BFFF
    )
    embed.set_footer(text="Sir Tim the Timely • DM Reminder Test")

    try:
        dm_channel = await ctx.client.rest.create_dm_channel(ctx.author.id)
        await ctx.client.rest.create_message(dm_channel.id, embed=embed)
        await ctx.respond("✅ DM reminder sent! Check your Discord DMs.", flags=hikari.MessageFlag.EPHEMERAL)
    except Exception as e:
        logger.error(f"Error sending DM reminder: {e}")
        await ctx.respond("❌ Failed to send DM. Make sure your DMs are open.", flags=hikari.MessageFlag.EPHEMERAL)

@admin.include
@arc.slash_subcommand("status", "Show bot status information")
async def status_info(ctx: arc.GatewayContext) -> None:
    """Show status information about the bot's components."""
    db_manager = ctx.client.get_type_dependency(DatabaseManager)
    reminder_system = ctx.client.get_type_dependency(ReminderSystem)
    
    await ctx.defer()
    
    try:
        # Get deadline stats
        deadlines = await db_manager.get_deadlines()
        upcoming = await db_manager.get_upcoming_deadlines(7)
        
        # Get reminder system stats
        reminder_stats = reminder_system.get_status()
        
        embed = hikari.Embed(
            title="📊 Sir Tim the Timely - Status",
            description="Current system status and statistics",
            color=0x00FF00,
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(
            name="Deadline Statistics",
            value=(
                f"• Total Deadlines: {len(deadlines)}\n"
                f"• Upcoming (7 days): {len(upcoming)}\n"
            ),
            inline=True
        )
        
        embed.add_field(
            name="Reminder System",
            value=(
                f"• Configured Channels: {reminder_stats.get('configured_channels', 0)}\n"
                f"• Last Daily Reminder: {reminder_stats.get('last_daily_reminder', 'None')}\n"
                f"• Reminder Time: {reminder_stats.get('daily_reminder_time', 'Unknown')}\n"
            ),
            inline=True
        )
        
        embed.set_footer(text="Sir Tim the Timely • Admin Panel")
        
        await ctx.respond(embed=embed, flags=hikari.MessageFlag.EPHEMERAL)
        
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        await ctx.respond(f"❌ Error retrieving status information: {str(e)}", flags=hikari.MessageFlag.EPHEMERAL)

@admin.include
@arc.slash_subcommand("cleanup", "Clean up duplicate and old deadlines")
async def cleanup_deadlines(ctx: arc.GatewayContext) -> None:
    """Clean up duplicate and old deadlines from the database."""
    db_manager = ctx.client.get_type_dependency(DatabaseManager)
    
    await ctx.defer()
    
    try:
        # Clean up old deadlines (older than 30 days)
        old_removed = await db_manager.cleanup_old_deadlines(30)
        
        # Find potential duplicates
        duplicates = await db_manager.find_duplicate_deadlines()
        
        embed = hikari.Embed(
            title="🧹 Deadline Cleanup Results",
            description="Database cleanup completed",
            color=0x00BFFF,
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(
            name="Old Deadlines Removed",
            value=f"Removed {old_removed} deadlines older than 30 days",
            inline=False
        )
        
        if duplicates:
            duplicate_text = []
            for dup in duplicates[:10]:  # Show first 10 duplicates
                duplicate_text.append(f"• ID {dup['id1']}: {dup['title1'][:50]}...")
                duplicate_text.append(f"  vs ID {dup['id2']}: {dup['title2'][:50]}...")
            
            if len(duplicates) > 10:
                duplicate_text.append(f"... and {len(duplicates) - 10} more")
            
            embed.add_field(
                name=f"Potential Duplicates Found ({len(duplicates)})",
                value="\n".join(duplicate_text) if duplicate_text else "None",
                inline=False
            )
            
            embed.add_field(
                name="Manual Review Required",
                value="Use `/admin mergedeadlines <keep_id> <remove_id>` to merge duplicates",
                inline=False
            )
        else:
            embed.add_field(
                name="Duplicates",
                value="No potential duplicates found",
                inline=False
            )
        
        embed.set_footer(text="Sir Tim the Timely • Admin Panel")
        
        await ctx.respond(embed=embed, flags=hikari.MessageFlag.EPHEMERAL)
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        await ctx.respond(f"❌ Error during cleanup: {str(e)}", flags=hikari.MessageFlag.EPHEMERAL)

@admin.include
@arc.slash_subcommand("mergedeadlines", "Merge two duplicate deadlines")
async def merge_deadlines(ctx: arc.GatewayContext) -> None:
    """Merge two duplicate deadlines by keeping one and removing the other."""
    db_manager = ctx.client.get_type_dependency(DatabaseManager)
    
    # Default values - in a real implementation, these would be options
    keep_id = 1
    remove_id = 2
    
    try:
        # Get deadline details before merging
        deadlines = await db_manager.get_deadlines(active_only=False)
        keep_deadline = next((d for d in deadlines if d['id'] == keep_id), None)
        remove_deadline = next((d for d in deadlines if d['id'] == remove_id), None)
        
        if not keep_deadline or not remove_deadline:
            await ctx.respond("❌ One or both deadline IDs not found. Please check the IDs and try again.", flags=hikari.MessageFlag.EPHEMERAL)
            return
        
        # Perform the merge
        success = await db_manager.merge_deadlines(keep_id, remove_id)
        
        if success:
            embed = hikari.Embed(
                title="✅ Deadlines Merged Successfully",
                description="Merged duplicate deadlines",
                color=0x00FF00,
                timestamp=datetime.now(timezone.utc)
            )
            
            embed.add_field(
                name="Kept Deadline",
                value=f"ID {keep_id}: {keep_deadline['title']}",
                inline=False
            )
            
            embed.add_field(
                name="Removed Deadline",
                value=f"ID {remove_id}: {remove_deadline['title']}",
                inline=False
            )
            
            embed.set_footer(text="Sir Tim the Timely • Admin Panel")
            
            await ctx.respond(embed=embed, flags=hikari.MessageFlag.EPHEMERAL)
        else:
            await ctx.respond("❌ Failed to merge deadlines. Please check the IDs and try again.", flags=hikari.MessageFlag.EPHEMERAL)
        
    except Exception as e:
        logger.error(f"Error merging deadlines: {e}")
        await ctx.respond(f"❌ Error merging deadlines: {str(e)}", flags=hikari.MessageFlag.EPHEMERAL)

@admin.include
@arc.slash_subcommand("testdigest", "Send a test weekly digest")
async def test_digest(ctx: arc.GatewayContext) -> None:
    """Send a test weekly digest to the current channel."""
    reminder_system = ctx.client.get_type_dependency(ReminderSystem)
    
    try:
        # Defer immediately to prevent timeout
        await ctx.defer(flags=hikari.MessageFlag.EPHEMERAL)
        
        # Temporarily set this channel as a reminder channel
        original_channels = reminder_system.reminder_channels.copy()
        reminder_system.reminder_channels[ctx.guild_id] = ctx.channel_id
        
        # Send the digest
        await reminder_system._send_weekly_digest()
        
        # Restore original channels
        reminder_system.reminder_channels = original_channels
        
        await ctx.respond("✅ Test weekly digest sent successfully!", flags=hikari.MessageFlag.EPHEMERAL)
            
    except NotFoundError:
        logger.error("Discord interaction not found for testdigest")
        return
    except BadRequestError:
        logger.error("Discord interaction already acknowledged for testdigest")
        return
    except Exception as e:
        logger.error(f"Error sending test digest: {e}")
        try:
            await ctx.respond(f"❌ Error sending test digest: {str(e)}", flags=hikari.MessageFlag.EPHEMERAL)
        except (NotFoundError, BadRequestError):
            pass

@admin.include
@arc.slash_subcommand("setrole", "Set the role to ping for reminders and digests")
async def set_reminder_role(
    ctx: arc.GatewayContext,
    role: arc.Option[hikari.Role, arc.RoleParams("Role to ping for reminders")]
) -> None:
    """Set the role to ping for reminders and weekly digests."""
    reminder_system = ctx.client.get_type_dependency(ReminderSystem)
    
    try:
        # Update the reminder role
        reminder_system.reminder_role_id = str(role.id)
        
        await ctx.respond(f"✅ Reminder role set to {role.mention}. This role will be pinged for weekly digests and urgent reminders.", flags=hikari.MessageFlag.EPHEMERAL)
        
    except Exception as e:
        logger.error(f"Error setting reminder role: {e}")
        await ctx.respond(f"❌ Error setting reminder role: {str(e)}", flags=hikari.MessageFlag.EPHEMERAL)

@admin.include
@arc.slash_subcommand("testrant", "Send a test random rant")
async def test_rant(ctx: arc.GatewayContext) -> None:
    """Send a test random rant to the current channel."""
    chat_handler = ctx.client.get_type_dependency(GeminiChatHandler)
    
    if not chat_handler:
        await ctx.respond("❌ Chat handler not available.", flags=hikari.MessageFlag.EPHEMERAL)
        return
    
    try:
        await ctx.defer(flags=hikari.MessageFlag.EPHEMERAL)
        
        # Send a random rant to the current channel
        await chat_handler._send_random_rant(ctx.channel_id)
        
        await ctx.respond("✅ Test rant sent successfully!", flags=hikari.MessageFlag.EPHEMERAL)
            
    except Exception as e:
        logger.error(f"Error sending test rant: {e}")
        await ctx.respond(f"❌ Error sending test rant: {str(e)}", flags=hikari.MessageFlag.EPHEMERAL)

@arc.loader
def load(client: arc.GatewayClient) -> None:
    """Load the plugin."""
    client.add_plugin(plugin)

@arc.unloader
def unload(client: arc.GatewayClient) -> None:
    """Unload the plugin."""
    client.remove_plugin(plugin)
