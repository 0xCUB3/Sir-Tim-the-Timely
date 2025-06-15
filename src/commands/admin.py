"""
Admin Command Module for Sir Tim the Timely

Implements admin commands for managing the bot and its settings.
"""

import logging
from datetime import datetime
from typing import Optional

import hikari
import arc

from ..database import DatabaseManager
from ..scraper import MITDeadlineScraper
from ..reminder_system import ReminderSystem

logger = logging.getLogger("sir_tim.commands.admin")

# Create a plugin for admin commands
plugin = arc.GatewayPlugin("admin")

# Define admin command group
admin = plugin.include_slash_group("admin", "Administrative commands for bot management")

@admin.include
@arc.slash_subcommand("scrape", "Manually trigger deadline scraping")
async def scrape_deadlines(ctx: arc.GatewayContext) -> None:
    """Manually trigger deadline scraping from MIT website."""
    # Only allow server admins to use this command
    if not ctx.member or not ctx.member.permissions.ADMINISTRATOR:
        await ctx.respond("This command can only be used by server administrators.", flags=hikari.MessageFlag.EPHEMERAL)
        return
    
    scraper = ctx.client.get_type_dependency(MITDeadlineScraper)
    
    await ctx.defer()
    
    try:
        await ctx.respond("Starting deadline scraping from MIT website...")
        
        # Perform scraping
        deadlines = await scraper.scrape_deadlines()
        
        # Send result
        await ctx.respond(f"✅ Successfully scraped {len(deadlines)} deadlines from the MIT website!")
        
    except Exception as e:
        logger.error(f"Error during manual scraping: {e}")
        await ctx.respond(f"❌ Error scraping deadlines: {str(e)}")

@admin.include
@arc.slash_subcommand("reminderchannel", "Set the channel for daily reminders")
async def set_reminder_channel(ctx: arc.GatewayContext) -> None:
    """Set the current channel for daily reminders."""
    # Only allow server admins to use this command
    if not ctx.member or not ctx.member.permissions.ADMINISTRATOR:
        await ctx.respond("This command can only be used by server administrators.", flags=hikari.MessageFlag.EPHEMERAL)
        return
    
    reminder_system = ctx.client.get_type_dependency(ReminderSystem)
    
    try:
        await reminder_system.set_reminder_channel(ctx.guild_id, ctx.channel_id)
        
        await ctx.respond("✅ This channel has been set as the reminder channel.")
        
    except Exception as e:
        logger.error(f"Error setting reminder channel: {e}")
        await ctx.respond(f"❌ Error setting reminder channel: {str(e)}")

@admin.include
@arc.slash_subcommand("adddeadline", "Add a custom deadline")
async def add_deadline(ctx: arc.GatewayContext) -> None:
    """Add a custom deadline to the database."""
    # Only allow server admins to use this command
    if not ctx.member or not ctx.member.permissions.ADMINISTRATOR:
        await ctx.respond("This command can only be used by server administrators.", flags=hikari.MessageFlag.EPHEMERAL)
        return
    
    db_manager = ctx.client.get_type_dependency(DatabaseManager)
    
    # Default values - in a real implementation, these would be options
    title = "Test Deadline"
    description = "This is a test deadline"
    due_date = datetime.now()
    category = "General"
    is_critical = False
    
    try:
        # Add the deadline
        deadline_id = await db_manager.add_deadline(
            title=title,
            description=description,
            due_date=due_date,
            category=category,
            is_critical=is_critical
        )
        
        await ctx.respond(f"✅ Added custom deadline: **{title}** with ID: {deadline_id}")
        
    except Exception as e:
        logger.error(f"Error adding custom deadline: {e}")
        await ctx.respond(f"❌ Error adding deadline: {str(e)}")

@admin.include
@arc.slash_subcommand("testreminder", "Send a test reminder")
async def test_reminder(ctx: arc.GatewayContext) -> None:
    """Send a test reminder to the current channel."""
    # Only allow server admins to use this command
    if not ctx.member or not ctx.member.permissions.ADMINISTRATOR:
        await ctx.respond("This command can only be used by server administrators.", flags=hikari.MessageFlag.EPHEMERAL)
        return
    
    reminder_system = ctx.client.get_type_dependency(ReminderSystem)
    
    await ctx.defer()
    
    try:
        result = await reminder_system.send_test_reminder(ctx.channel_id)
        
        if result:
            await ctx.respond("✅ Test reminder sent successfully!")
        else:
            await ctx.respond("❌ Failed to send test reminder.")
        
    except Exception as e:
        logger.error(f"Error sending test reminder: {e}")
        await ctx.respond(f"❌ Error: {str(e)}")

@admin.include
@arc.slash_subcommand("status", "Show bot status information")
async def status_info(ctx: arc.GatewayContext) -> None:
    """Show status information about the bot's components."""
    # Only allow server admins to use this command
    if not ctx.member or not ctx.member.permissions.ADMINISTRATOR:
        await ctx.respond("This command can only be used by server administrators.", flags=hikari.MessageFlag.EPHEMERAL)
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
            timestamp=datetime.now()
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
        
        await ctx.respond(embed=embed)
        
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        await ctx.respond(f"❌ Error retrieving status information: {str(e)}")

@admin.include
@arc.slash_subcommand("cleanup", "Clean up duplicate and old deadlines")
async def cleanup_deadlines(ctx: arc.GatewayContext) -> None:
    """Clean up duplicate and old deadlines from the database."""
    # Only allow server admins to use this command
    if not ctx.member or not ctx.member.permissions.ADMINISTRATOR:
        await ctx.respond("This command can only be used by server administrators.", flags=hikari.MessageFlag.EPHEMERAL)
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
            timestamp=datetime.now()
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
        
        await ctx.respond(embed=embed)
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        await ctx.respond(f"❌ Error during cleanup: {str(e)}")

@admin.include
@arc.slash_subcommand("mergedeadlines", "Merge two duplicate deadlines")
async def merge_deadlines(ctx: arc.GatewayContext) -> None:
    """Merge two duplicate deadlines by keeping one and removing the other."""
    # Only allow server admins to use this command
    if not ctx.member or not ctx.member.permissions.ADMINISTRATOR:
        await ctx.respond("This command can only be used by server administrators.", flags=hikari.MessageFlag.EPHEMERAL)
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
            await ctx.respond("❌ One or both deadline IDs not found. Please check the IDs and try again.")
            return
        
        # Perform the merge
        success = await db_manager.merge_deadlines(keep_id, remove_id)
        
        if success:
            embed = hikari.Embed(
                title="✅ Deadlines Merged Successfully",
                description=f"Merged duplicate deadlines",
                color=0x00FF00,
                timestamp=datetime.now()
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
            
            await ctx.respond(embed=embed)
        else:
            await ctx.respond("❌ Failed to merge deadlines. Please check the IDs and try again.")
        
    except Exception as e:
        logger.error(f"Error merging deadlines: {e}")
        await ctx.respond(f"❌ Error merging deadlines: {str(e)}")

@arc.loader
def load(client: arc.GatewayClient) -> None:
    """Load the plugin."""
    client.add_plugin(plugin)

@arc.unloader
def unload(client: arc.GatewayClient) -> None:
    """Unload the plugin."""
    client.remove_plugin(plugin)
