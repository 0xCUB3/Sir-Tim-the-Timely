"""
Admin Command Module for Sir Tim the Timely

Implements admin commands for managing the bot and its settings.
"""

import logging
from datetime import datetime, timezone
import pytz
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

# Define admin command group with authorization check
@arc.with_hook(arc.guild_only)
async def admin_check(ctx: arc.GatewayContext) -> bool:
    """Hook to check admin authorization before running commands."""
    if not is_admin_authorized(ctx.member):
        await ctx.respond("❌ You don't have permission to use admin commands.", flags=hikari.MessageFlag.EPHEMERAL)
        return False
    return True

admin = plugin.include_slash_group("admin", "Administrative commands for bot management", hooks=[admin_check])

@admin.include
@arc.slash_subcommand("addrole", "Add a role to the admin whitelist")
async def add_admin_role(
    ctx: arc.GatewayContext,
    role: arc.Option[hikari.Role, arc.RoleParams("Role to add to admin whitelist")]
) -> None:
    """Add a role to the admin command whitelist."""
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
            except:
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
        return
    
    db_manager = ctx.client.get_type_dependency(DatabaseManager)
    reminder_system = ctx.client.get_type_dependency(ReminderSystem)
    
    try:
        # Parse the due date
        try:
            naive_due_date = datetime.strptime(due_date, "%Y-%m-%d %H:%M")
            # Localize the naive datetime to the default timezone of the bot
            local_due_date = reminder_system.default_timezone.localize(naive_due_date)
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
        return
    
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
@arc.slash_subcommand("status", "Show bot status information")
async def status_info(ctx: arc.GatewayContext) -> None:
    """Show status information about the bot's components."""
        return
    
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
        return
    
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
        return
    
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
        return
    
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
        return
    
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
        return
    
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
