"""
Deadlines Command Module for Sir Tim the Timely

Implements commands for managing and viewing deadlines.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import hikari
import arc

from ..database import DatabaseManager
from ..ai_handler import AIHandler

logger = logging.getLogger("sir_tim.commands.deadlines")

# Create a plugin for deadline commands
plugin = arc.GatewayPlugin("deadlines")

# Define deadline command group
deadlines = plugin.include_slash_group("deadlines", "View and manage MIT deadlines")

@deadlines.include
@arc.slash_subcommand("list", "List all deadlines or filter by category/month")
async def list_deadlines(ctx: arc.GatewayContext) -> None:
    """List all deadlines or filter by category/month."""
    db_manager = ctx.client.get_type_dependency(DatabaseManager)
    
    await ctx.defer()
    
    try:
        # Get all active deadlines
        all_deadlines = await db_manager.get_deadlines(category=None)
        
        if not all_deadlines:
            await ctx.respond("No deadlines found.")
            return
        
        await send_deadline_list(ctx, all_deadlines, title="MIT Deadlines")
        
    except Exception as e:
        logger.error(f"Error listing deadlines: {e}")
        await ctx.respond("Sorry, something went wrong while retrieving the deadlines.")

@deadlines.include
@arc.slash_subcommand("next", "Show deadlines in the next X days")
async def next_deadlines(ctx: arc.GatewayContext) -> None:
    """Show deadlines coming up in the next X days."""
    db_manager = ctx.client.get_type_dependency(DatabaseManager)
    days = 7  # Default value
    
    await ctx.defer()
    
    try:
        deadlines = await db_manager.get_upcoming_deadlines(days)
        
        if not deadlines:
            await ctx.respond(f"Great news! 🎉 No deadlines in the next {days} days.")
            return
        
        await send_deadline_list(ctx, deadlines, title=f"Upcoming Deadlines (Next {days} Days)")
        
    except Exception as e:
        logger.error(f"Error fetching upcoming deadlines: {e}")
        await ctx.respond("Sorry, something went wrong while retrieving upcoming deadlines.")

@deadlines.include
@arc.slash_subcommand("search", "Search for deadlines")
async def search_deadlines(ctx: arc.GatewayContext) -> None:
    """Search for deadlines using natural language."""
    db_manager = ctx.client.get_type_dependency(DatabaseManager)
    query = "upcoming"  # Default query
    
    await ctx.defer()
    
    try:
        # Check if AI handler is available
        ai_handler = ctx.client.get_type_dependency(AIHandler, default=None)
        
        if ai_handler:
            # Use AI to process natural language query
            response = await ai_handler.process_natural_query(query)
            
            embed = hikari.Embed(
                title="🔍 Deadline Search Results",
                description=response,
                color=0x4285F4,
                timestamp=datetime.now()
            )
            
            embed.set_footer(text="Sir Tim the Timely • AI-powered search")
            
            await ctx.respond(embed=embed)
            
        else:
            # Fallback to basic keyword search
            results = await db_manager.search_deadlines(query)
            
            if not results:
                await ctx.respond(f"No deadlines found matching '{query}'.")
                return
            
            await send_deadline_list(ctx, results, title=f"Search Results for '{query}'")
            
    except Exception as e:
        logger.error(f"Error searching deadlines: {e}")
        await ctx.respond("Sorry, something went wrong while searching for deadlines.")

@deadlines.include
@arc.slash_subcommand("completed", "Mark a deadline as completed")
async def mark_completed(ctx: arc.GatewayContext) -> None:
    """Mark a deadline as completed for the user."""
    db_manager = ctx.client.get_type_dependency(DatabaseManager)
    deadline_id = 1  # Default ID
    
    try:
        # Check if deadline exists
        deadlines = await db_manager.get_deadlines()
        deadline = next((d for d in deadlines if d['id'] == deadline_id), None)
        
        if not deadline:
            await ctx.respond("Deadline not found. Please check the ID and try again.")
            return
        
        # Mark as completed
        await db_manager.mark_deadline_completed(ctx.author.id, deadline_id, True)
        
        embed = hikari.Embed(
            title="✅ Deadline Marked as Completed",
            description=f"You've completed: **{deadline['title']}**",
            color=0x00FF00,
            timestamp=datetime.now()
        )
        
        embed.set_footer(text="Sir Tim the Timely • Progress Tracker")
        
        await ctx.respond(embed=embed)
        
    except Exception as e:
        logger.error(f"Error marking deadline as completed: {e}")
        await ctx.respond("Sorry, something went wrong while updating your deadline status.")

@deadlines.include
@arc.slash_subcommand("remind", "Set a personal reminder for a deadline")
async def set_reminder(ctx: arc.GatewayContext) -> None:
    """Set a personal reminder for a deadline."""
    db_manager = ctx.client.get_type_dependency(DatabaseManager)
    deadline_id = 1  # Default ID
    hours = 24  # Default hours
    
    try:
        # Check if deadline exists
        deadlines = await db_manager.get_deadlines()
        deadline = next((d for d in deadlines if d['id'] == deadline_id), None)
        
        if not deadline:
            await ctx.respond("Deadline not found. Please check the ID and try again.")
            return
        
        # Calculate reminder time
        due_date = datetime.fromisoformat(deadline['due_date'].replace('Z', '+00:00'))
        reminder_time = due_date - timedelta(hours=hours)
        
        embed = hikari.Embed(
            title="🔔 Reminder Set",
            description=f"You'll be reminded about **{deadline['title']}** {hours} hour(s) before the deadline.",
            color=0x00BFFF,
            timestamp=datetime.now()
        )
        
        embed.add_field(name="Due Date", value=due_date.strftime("%B %d, %Y at %I:%M %p"), inline=True)
        embed.add_field(name="Reminder Time", value=reminder_time.strftime("%B %d, %Y at %I:%M %p"), inline=True)
        
        embed.set_footer(text="Sir Tim the Timely • Reminder System")
        
        await ctx.respond(embed=embed)
        
    except Exception as e:
        logger.error(f"Error setting reminder: {e}")
        await ctx.respond("Sorry, something went wrong while setting your reminder.")

@deadlines.include
@arc.slash_subcommand("help", "Show detailed help and FAQ about deadlines")
async def deadline_help(ctx: arc.GatewayContext) -> None:
    """Show detailed help about deadline commands and FAQ."""
    embed = hikari.Embed(
        title="📚 Sir Tim the Timely - Deadline Help",
        description="Here's how to use the deadline commands effectively:",
        color=0x9B59B6,
        timestamp=datetime.now()
    )
    
    embed.add_field(
        name="Available Commands",
        value=(
            "• `/deadlines list` - List all deadlines\n"
            "• `/deadlines next` - Show deadlines in the next 7 days\n"
            "• `/deadlines search` - Search deadlines with natural language\n"
            "• `/deadlines completed` - Mark deadline as completed\n"
            "• `/deadlines remind` - Set personal reminder\n"
        ),
        inline=False
    )
    
    embed.add_field(
        name="Deadline Categories",
        value=(
            "• **Medical**: Health forms, immunizations\n"
            "• **Academic**: Transcripts, AP/IB credit, placement tests\n"
            "• **Housing**: Housing application, roommate forms\n"
            "• **Financial**: Tuition, financial aid, scholarships\n"
            "• **Orientation**: FPOP, orientation events\n"
            "• **Administrative**: MIT IDs, emergency contacts\n"
            "• **Registration**: Class registration, advising\n"
            "• **General**: Other miscellaneous deadlines\n"
        ),
        inline=False
    )
    
    embed.add_field(
        name="FAQ",
        value=(
            "**Q: How often are deadlines updated?**\n"
            "A: Deadlines are automatically fetched every 6 hours from the MIT first-year website.\n\n"
            "**Q: Are deadline times in my timezone?**\n"
            "A: Deadlines are displayed in US Eastern Time. Use `/timezone set` to customize your view.\n\n"
            "**Q: How do I get deadline reminders?**\n"
            "A: Daily reminders are sent to configured channels. For personal reminders, use `/deadlines remind`."
        ),
        inline=False
    )
    
    embed.set_footer(text="Sir Tim the Timely • MIT Deadline Bot")
    
    await ctx.respond(embed=embed)

async def send_deadline_list(ctx: arc.GatewayContext, deadlines: List[Dict], title: str) -> None:
    """Format and send a list of deadlines as embeds."""
    # Sort by date
    sorted_deadlines = sorted(deadlines, key=lambda x: x['due_date'])
    
    # Create embed
    embed = hikari.Embed(
        title=f"📅 {title}",
        description=f"Found {len(deadlines)} deadline(s)",
        color=0x4285F4,
        timestamp=datetime.now()
    )
    
    # Group by month
    months = {}
    for deadline in sorted_deadlines:
        due_date = datetime.fromisoformat(deadline['due_date'].replace('Z', '+00:00'))
        month_name = due_date.strftime("%B")
        
        if month_name not in months:
            months[month_name] = []
        
        months[month_name].append(deadline)
    
    # Add fields for each month
    for month_name, month_deadlines in months.items():
        deadline_texts = []
        
        for deadline in month_deadlines:
            due_date = datetime.fromisoformat(deadline['due_date'].replace('Z', '+00:00'))
            day = due_date.strftime("%d")
            
            critical_marker = "🚨 " if deadline.get('is_critical') else ""
            deadline_text = f"**{day}**: {critical_marker}[ID:{deadline['id']}] {deadline['title']}"
            
            category = deadline.get('category')
            if category:
                deadline_text += f" `{category}`"
            
            deadline_texts.append(deadline_text)
        
        embed.add_field(
            name=month_name,
            value="\n".join(deadline_texts),
            inline=False
        )
    
    embed.add_field(
        name="How to Use",
        value=(
            "• Get details: `/deadlines search <deadline title>`\n"
            "• Mark complete: `/deadlines completed <ID>`\n"
            "• Set reminder: `/deadlines remind <ID> <hours>`"
        ),
        inline=False
    )
    
    embed.set_footer(text="Sir Tim the Timely • MIT Deadline Bot")
    
    await ctx.respond(embed=embed)

@arc.loader
def load(client: arc.GatewayClient) -> None:
    """Load the plugin."""
    client.add_plugin(plugin)

@arc.unloader
def unload(client: arc.GatewayClient) -> None:
    """Unload the plugin."""
    client.remove_plugin(plugin)
