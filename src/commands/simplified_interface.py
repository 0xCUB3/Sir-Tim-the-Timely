"""
Simplified Interface for Sir Tim the Timely

This module provides a streamlined user experience with minimal commands
and intelligent defaults to reduce user cognitive load.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
import re

import hikari
import arc
import miru
from miru.ext import nav
from hikari.errors import NotFoundError, BadRequestError

from ..database import DatabaseManager
from ..ai_handler import AIHandler

logger = logging.getLogger("sir_tim.commands.simplified")

# Create a plugin for the simplified interface
plugin = arc.GatewayPlugin("simplified")

# Custom button and view for "View All Deadlines"
class ViewAllDeadlinesButton(miru.Button):
    def __init__(self):
        super().__init__(
            style=hikari.ButtonStyle.LINK,
            label="🌐 View All Deadlines"
        )
        self.url = os.getenv("MIT_DEADLINES_URL", "https://firstyear.mit.edu/orientation/countdown-to-campus-before-you-arrive/critical-summer-actions-and-deadlines/")

class ViewAllDeadlinesView(miru.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(ViewAllDeadlinesButton())

async def safe_defer_and_respond(ctx: arc.GatewayContext, func):
    """Safely defer and execute a function with error handling."""
    try:
        await ctx.defer()
        return await func()
    except NotFoundError:
        logger.error("Discord interaction not found")
        return
    except BadRequestError:
        logger.error("Discord interaction already acknowledged")
        return
    except Exception as e:
        logger.error(f"Error in command: {e}")
        try:
            await ctx.respond("Sorry, something went wrong. Please try again.")
        except (NotFoundError, BadRequestError):
            pass

# Main command - handles everything with AI
@plugin.include
@arc.slash_command("tim", "Ask Tim anything about deadlines or get quick info")
async def tim_main(
    ctx: arc.GatewayContext,
    query: arc.Option[str, arc.StrParams("What would you like to know? (e.g., 'what's due soon?', 'housing deadlines')")] = None
) -> None:
    """
    Main command that handles all deadline queries intelligently.
    
    Examples:
    - /tim what's due this week?
    - /tim housing deadlines
    - /tim help
    - /tim (no query - shows upcoming deadlines)
    """
    async def execute():
        db_manager = ctx.client.get_type_dependency(DatabaseManager)
        ai_handler = ctx.client.get_type_dependency(AIHandler, default=None)
        
        # If no query provided, show all deadlines (changed from upcoming only)
        if not query:
            deadlines = await db_manager.get_deadlines()
            if not deadlines:
                embed = hikari.Embed(
                    title="🎉 Great News!",
                    description="No deadlines found.",
                    color=0x00FF00,
                    timestamp=datetime.now(timezone.utc)
                )
                view = ViewAllDeadlinesView()
                await ctx.respond(embed=embed, components=view)
                return
            await send_smart_deadline_list(ctx, deadlines, "📅 All MIT Deadlines")
            return
        
        # Handle special queries
        query_lower = query.lower().strip()
        
        # Help queries
        if any(word in query_lower for word in ['help', 'commands', 'how', 'what can']):
            await show_quick_help(ctx)
            return
        
        # Settings queries
        if any(word in query_lower for word in ['settings', 'timezone', 'preferences', 'remind me']):
            await show_quick_settings(ctx)
            return
        
        # Use AI for natural language processing if available
        if ai_handler:
            # Show typing while AI processes the query
            async with ctx.client.rest.trigger_typing(ctx.channel_id):
                response = await ai_handler.process_natural_query(query)
                embed = hikari.Embed(
                    title="🤖 Tim's Response",
                    description=response,
                    color=0x4285F4,
                    timestamp=datetime.now(timezone.utc)
                )
                embed.set_footer(text="💡 Tip: Try '/tim' with no text to see all deadlines")
                
                # Add view with button
                view = ViewAllDeadlinesView()
                await ctx.respond(embed=embed, components=view)
        else:
            # Fallback to keyword search
            results = await db_manager.search_deadlines(query)
            if not results:
                await ctx.respond(f"No deadlines found for '{query}'. Try '/tim help' for examples.")
                return
            await send_smart_deadline_list(ctx, results, f"🔍 Search Results for '{query}'")
    
    await safe_defer_and_respond(ctx, execute)

# Quick access command for immediate deadlines
@plugin.include
@arc.slash_command("urgent", "Show urgent deadlines (next 3 days)")
async def urgent_deadlines(ctx: arc.GatewayContext) -> None:
    """Show deadlines that are urgent (next 3 days)."""
    async def execute():
        db_manager = ctx.client.get_type_dependency(DatabaseManager)
        deadlines = await db_manager.get_upcoming_deadlines(3)
        
        if not deadlines:
            embed = hikari.Embed(
                title="✅ All Clear!",
                description="No urgent deadlines in the next 3 days.",
                color=0x00FF00,
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(
                name="What's Next?",
                value="Use `/tim` to see what's coming up this week.",
                inline=False
            )
            view = ViewAllDeadlinesView()
            await ctx.respond(embed=embed, components=view)
            return
        
        await send_smart_deadline_list(ctx, deadlines, "🚨 Urgent Deadlines (Next 3 Days)")
    
    await safe_defer_and_respond(ctx, execute)

# One-click setup command
@plugin.include
@arc.slash_command("setup", "Quick setup for notifications and preferences")
async def quick_setup(ctx: arc.GatewayContext) -> None:
    """Quick setup wizard for new users."""
    async def execute():
        db_manager = ctx.client.get_type_dependency(DatabaseManager)
        
        # Set sensible defaults
        await db_manager.update_user_preferences(
            user_id=ctx.author.id,
            timezone="US/Eastern",  # MIT timezone
            daily_reminder_time="09:00",
            reminder_enabled=True
        )
        
        embed = hikari.Embed(
            title="Setup Complete!",
            description="Tim is now configured with smart defaults for MIT students.",
            color=0x00BFFF,
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(
            name="Your Settings",
            value=(
                "• **Timezone**: US/Eastern (MIT time)\n"
                "• **Daily Reminders**: 9:00 AM\n"
                "• **Notifications**: Enabled\n"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Getting Started",
            value=(
                "• Type `/tim` to see upcoming deadlines\n"
                "• Type `/urgent` for urgent deadlines\n"
                "• Ask Tim questions like '/tim housing deadlines'\n"
            ),
            inline=False
        )
        
        embed.set_footer(text="You can change these settings anytime with '/tim settings'")
        await ctx.respond(embed=embed)
    
    await safe_defer_and_respond(ctx, execute)

async def send_smart_deadline_list(ctx: arc.GatewayContext, deadlines: List[Dict], title: str) -> None:
    """Send a simplified, user-friendly deadline list."""
    if not deadlines:
        embed = hikari.Embed(
            title=title,
            description="No deadlines found.",
            color=0x4285F4,
            timestamp=datetime.now(timezone.utc)
        )
        await ctx.respond(embed=embed)
        return
    
    # Sort by urgency and date
    sorted_deadlines = sorted(deadlines, key=lambda x: x['due_date'])
    
    # For urgent view, show all on one page. For regular view, paginate if needed
    is_urgent = "urgent" in title.lower()
    per_page = len(sorted_deadlines) if is_urgent else 6
    
    pages = []
    total = len(sorted_deadlines)
    
    for i in range(0, total, per_page):
        page_deadlines = sorted_deadlines[i:i+per_page]
        page_num = (i // per_page) + 1
        total_pages = (total + per_page - 1) // per_page
        
        embed = hikari.Embed(
            title=title,
            color=0x4285F4,
            timestamp=datetime.now(timezone.utc)
        )
        
        if total_pages > 1:
            embed.description = f"Page {page_num} of {total_pages} • Showing {len(page_deadlines)} of {total} deadlines"
        else:
            embed.description = f"Showing {len(page_deadlines)} deadline{'s' if len(page_deadlines) != 1 else ''}"
        
        for dl in page_deadlines:
            # Parse due date and time
            due_date_raw = dl.get('due_date')
            if due_date_raw:
                try:
                    due_date = datetime.fromisoformat(due_date_raw.replace('Z', '+00:00'))
                    days_until = (due_date.date() - datetime.now(timezone.utc).date()).days
                    
                    # Format date and time
                    date_str = due_date.strftime('%B %d, %Y')
                    time_str = due_date.strftime('%I:%M %p EST')
                    
                    # Determine urgency status and circle color
                    if days_until < 0:
                        status_circle = "🔴"  # Red for overdue
                        urgency_note = f"Was due {abs(days_until)} day{'s' if abs(days_until) != 1 else ''} ago"
                    elif days_until == 0:
                        status_circle = "🔴"  # Red for due today
                        urgency_note = "Due today"
                    elif days_until == 1:
                        status_circle = "🔴"  # Red for due tomorrow
                        urgency_note = "Due tomorrow"
                    elif days_until <= 3:
                        status_circle = "🔴"  # Red for urgent (next 3 days)
                        urgency_note = f"Due in {days_until} days"
                    elif days_until <= 7:
                        status_circle = "🟠"  # Orange for this week
                        urgency_note = f"Due in {days_until} days"
                    else:
                        status_circle = "🟠"  # Orange for upcoming
                        urgency_note = f"Due in {days_until} days"
                    
                    full_date_time = f"{date_str} at {time_str}"
                    
                except Exception:
                    status = "UNKNOWN"
                    urgency_note = "Date unknown"
                    full_date_time = "Date and time unknown"
            else:
                status = "UNKNOWN"
                urgency_note = "Date unknown"
                full_date_time = "Date and time unknown"
            
            title_str = dl.get('title', 'Untitled')
            category = dl.get('category', 'General')
            
            # Clean up description
            desc = dl.get('description', '').strip()
            if desc and len(desc) > 150:
                desc = desc[:147] + "..."
            
            # Create field value (removed status line, added circle to title)
            field_value = f"📅 **Due:** {full_date_time}\n📂 **Category:** {category}"
            if desc:
                field_value += f"\n📝 **Details:** {desc}"
            
            # Add link if available
            url = dl.get('url')
            if url and url.strip() and url.lower() != 'no url available':
                field_value += f"\n🔗 **Link:** {url}"
            
            embed.add_field(
                name=f"{status_circle} {title_str}",
                value=field_value,
                inline=False
            )
        
        if not is_urgent:
            embed.set_footer(text="💡 Use '/urgent' for urgent deadlines or '/tim help' for more options")
        else:
            embed.set_footer(text="💡 Use '/tim' to see all upcoming deadlines")
        
        pages.append(embed)
    
    # Send response with "View All Deadlines" button
    if len(pages) == 1:
        # Create view with button for single page
        view = ViewAllDeadlinesView()
        await ctx.respond(embed=pages[0], components=view)
    else:
        # Create navigator for multiple pages (without adding incompatible button)
        miru_client = ctx.client.get_type_dependency(miru.Client)
        buttons = [nav.PrevButton(), nav.IndicatorButton(), nav.NextButton(), nav.StopButton()]
        navigator = nav.NavigatorView(pages=pages, items=buttons, timeout=300)
        
        # Add the "View All Deadlines" button to each page footer instead
        for page in pages:
            current_footer = page.footer.text if page.footer else ""
            if current_footer:
                page.set_footer(text=f"{current_footer} • 🌐 View all: {os.getenv('MIT_DEADLINES_URL', 'https://firstyear.mit.edu/orientation/countdown-to-campus-before-you-arrive/critical-summer-actions-and-deadlines/')}")
            else:
                page.set_footer(text=f"🌐 View all deadlines: {os.getenv('MIT_DEADLINES_URL', 'https://firstyear.mit.edu/orientation/countdown-to-campus-before-you-arrive/critical-summer-actions-and-deadlines/')}")
        
        builder = await navigator.build_response_async(miru_client)
        await ctx.respond_with_builder(builder)
        miru_client.start_view(navigator)

async def show_quick_help(ctx: arc.GatewayContext) -> None:
    """Show simplified help information."""
    embed = hikari.Embed(
        title="How to Use Tim",
        description="Tim makes deadline tracking simple! Here's what you can do:",
        color=0x9B59B6,
        timestamp=datetime.now(timezone.utc)
    )
    
    embed.add_field(
        name="Quick Commands",
        value=(
            "• `/tim` - See upcoming deadlines\n"
            "• `/urgent` - Show urgent deadlines (next 3 days)\n"
            "• `/setup` - Quick setup for new users\n"
        ),
        inline=False
    )
    
    embed.add_field(
        name="Ask Tim Anything",
        value=(
            "• `/tim what's due this week?`\n"
            "• `/tim housing deadlines`\n"
            "• `/tim medical forms`\n"
            "• `/tim help with financial aid`\n"
        ),
        inline=False
    )
    
    embed.add_field(
        name="Settings",
        value="• `/tim settings` - Manage notifications and timezone",
        inline=False
    )
    
    embed.set_footer(text="Tim understands natural language - just ask!")
    await ctx.respond(embed=embed)

async def show_quick_settings(ctx: arc.GatewayContext) -> None:
    """Show simplified settings interface."""
    db_manager = ctx.client.get_type_dependency(DatabaseManager)
    
    # Get current preferences
    prefs = await db_manager.get_user_preferences(ctx.author.id)
    
    embed = hikari.Embed(
        title="Your Settings",
        description="Current notification and timezone settings:",
        color=0x00BFFF,
        timestamp=datetime.now(timezone.utc)
    )
    
    embed.add_field(
        name="Current Settings",
        value=(
            f"• **Timezone**: {prefs.get('timezone', 'US/Eastern')}\n"
            f"• **Daily Reminders**: {prefs.get('daily_reminder_time', '9:00 AM')}\n"
            f"• **Notifications**: {'Enabled' if prefs.get('reminder_enabled', True) else 'Disabled'}\n"
        ),
        inline=False
    )
    
    embed.add_field(
        name="Quick Actions",
        value=(
            "• Use `/setup` to reset to defaults\n"
            "• For advanced settings, contact an admin\n"
        ),
        inline=False
    )
    
    embed.set_footer(text="Most students use the default MIT timezone (US/Eastern)")
    await ctx.respond(embed=embed)

@arc.loader
def load(client: arc.GatewayClient) -> None:
    """Load the simplified interface plugin."""
    client.add_plugin(plugin)

@arc.unloader
def unload(client: arc.GatewayClient) -> None:
    """Unload the simplified interface plugin."""
    client.remove_plugin(plugin)