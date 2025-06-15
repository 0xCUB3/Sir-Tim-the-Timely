"""
Deadlines Command Module for Sir Tim the Timely

Implements commands for managing and viewing deadlines.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
import functools
import re

import hikari
import arc
import miru
from miru.ext import nav

from ..database import DatabaseManager
from ..ai_handler import AIHandler

logger = logging.getLogger("sir_tim.commands.deadlines")

# Create a plugin for deadline commands
plugin = arc.GatewayPlugin("deadlines")

# Define deadline command group
deadlines = plugin.include_slash_group("deadlines", "View and manage MIT deadlines")

def autodefer(func):
    @functools.wraps(func)
    async def wrapper(ctx, *args, **kwargs):
        await ctx.defer()
        return await func(ctx, *args, **kwargs)
    return wrapper

@deadlines.include
@arc.slash_subcommand("list", "List all deadlines or filter by category/month")
@autodefer
async def list_deadlines(ctx: arc.GatewayContext) -> None:
    """List all deadlines or filter by category/month."""
    db_manager = ctx.client.get_type_dependency(DatabaseManager)
    
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
                timestamp=datetime.now(timezone.utc)
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
            timestamp=datetime.now(timezone.utc)
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
        timestamp=datetime.now(timezone.utc)
    )
    
    embed.add_field(
        name="Available Commands",
        value=(
            "• `/deadlines list` - List all deadlines\n"
            "• `/deadlines next` - Show deadlines in the next 7 days\n"
            "• `/deadlines search` - Search deadlines with natural language\n"
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
    """Format and send a list of deadlines as interactive embeds with pagination buttons, using the stored AI-enhanced titles from the database. Do not re-enhance titles at display time."""
    sorted_deadlines = sorted(deadlines, key=lambda x: x['due_date'])
    total = len(sorted_deadlines)
    if total == 0:
        embed = hikari.Embed(
            title=f"📅 {title}",
            description="No deadlines found.",
            color=0x4285F4,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text="Sir Tim the Timely • MIT Deadline Bot")
        await ctx.respond(embed=embed)
        return

    per_page = 8
    pages = []

    def extract_all_dates_from_desc(desc):
        patterns = [
            r"([A-Za-z]+ \d{1,2},? \d{4})",
        ]
        found_dates = []
        for pat in patterns:
            for m in re.finditer(pat, desc, re.IGNORECASE):
                try:
                    found_dates.append(datetime.strptime(m.group(1).replace(',', ''), "%B %d %Y"))
                except Exception:
                    try:
                        found_dates.append(datetime.strptime(m.group(1).replace(',', ''), "%b %d %Y"))
                    except Exception:
                        continue
        return found_dates

    for i in range(0, total, per_page):
        page_deadlines = sorted_deadlines[i:i+per_page]
        page_num = (i // per_page) + 1
        total_pages = (total + per_page - 1) // per_page

        lines = []
        for dl in page_deadlines:
            start_date_raw = dl.get('start_date')
            due_date_raw = dl.get('due_date')
            start_date = None
            due_date = None
            if start_date_raw:
                try:
                    start_date = datetime.fromisoformat(start_date_raw.replace('Z', '+00:00'))
                except Exception:
                    start_date = None
            if due_date_raw:
                try:
                    due_date = datetime.fromisoformat(due_date_raw.replace('Z', '+00:00'))
                except Exception:
                    due_date = None
            desc = dl.get('description', '').strip()
            desc_dates = extract_all_dates_from_desc(desc)
            all_dates = [d for d in [start_date, due_date] if d]
            all_dates.extend(desc_dates)
            latest_date = max(all_dates) if all_dates else None
            if start_date and latest_date and start_date.date() != latest_date.date():
                type_emoji = "📅"
                type_label = "Active"
                date_str = f"{start_date.strftime('%b %d')}–{latest_date.strftime('%b %d, %Y')}"
            elif due_date and latest_date and due_date != latest_date:
                type_emoji = "📅"
                type_label = "Active"
                date_str = f"{due_date.strftime('%b %d')}–{latest_date.strftime('%b %d, %Y')}"
            elif latest_date:
                type_emoji = "⏰"
                type_label = "Due"
                date_str = latest_date.strftime('%b %d, %Y')
            elif start_date:
                type_emoji = "🟢"
                type_label = "Opens"
                date_str = start_date.strftime('%b %d, %Y')
            else:
                type_emoji = "❓"
                type_label = "Date"
                date_str = "Unknown"

            marker = "🚨 " if dl.get('is_critical') else ""
            title_str = dl.get('title', 'Untitled')
            category = dl.get('category', 'General')
            if desc:
                if len(desc) > 120:
                    desc = f"*{desc}*"
                else:
                    desc = f"{desc}"
            else:
                desc = "_No description available._"
            lines.append(
                f"{marker}{type_emoji} **{title_str}**  `#{dl['id']}`\n"
                f"> **{type_label}:** {date_str}   |   **Category:** `{category}`\n"
                f"> {desc}"
            )
        page_desc = "\n\n".join(lines)
        embed = hikari.Embed(
            title=f"📅 {title}",
            description=f"Page {page_num}/{total_pages} • Showing {i+1}-{min(i+per_page, total)} of {total} deadlines\n\n{page_desc}",
            color=0x4285F4,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text="Sir Tim the Timely • MIT Deadline Bot • AI-Enhanced")
        pages.append(embed)

    if len(pages) == 1:
        await ctx.respond(embed=pages[0])
    else:
        miru_client = ctx.client.get_type_dependency(miru.Client)
        buttons = [nav.FirstButton(), nav.PrevButton(), nav.IndicatorButton(), nav.NextButton(), nav.LastButton(), nav.StopButton()]
        navigator = nav.NavigatorView(pages=pages, items=buttons, timeout=300)
        builder = await navigator.build_response_async(miru_client)
        await ctx.respond_with_builder(builder)
        miru_client.start_view(navigator)

@arc.loader
def load(client: arc.GatewayClient) -> None:
    """Load the plugin."""
    client.add_plugin(plugin)

@arc.unloader
def unload(client: arc.GatewayClient) -> None:
    """Unload the plugin."""
    client.remove_plugin(plugin)
