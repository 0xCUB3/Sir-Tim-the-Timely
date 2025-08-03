"""
Deadlines Command Module for Sir Tim the Timely

Implements commands for managing and viewing deadlines.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict
import functools
import re

import hikari
import arc
import miru
from miru.ext import nav
from hikari.errors import NotFoundError, BadRequestError

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
        try:
            await ctx.defer()
            return await func(ctx, *args, **kwargs)
        except NotFoundError as e:
            logger.error(f"Discord interaction not found in {func.__name__}: {e}")
            return
        except BadRequestError as e:
            logger.error(f"Discord interaction already acknowledged in {func.__name__}: {e}")
            return
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            try:
                await ctx.respond("Sorry, something went wrong with this command.")
            except (NotFoundError, BadRequestError):
                pass
    return wrapper


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

# Main command - handles everything with AI (moved from simplified_interface)
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
        
        # If no query provided, show all deadlines using the detailed format
        if not query:
            deadlines = await db_manager.get_deadlines()
            if not deadlines:
                embed = hikari.Embed(
                    title="🎉 Great News!",
                    description="No deadlines found.",
                    color=0x00FF00,
                    timestamp=datetime.now(timezone.utc)
                )
                await ctx.respond(embed=embed)
                return
            # Regular detailed deadline list
            from ..commands.deadlines import send_deadline_list
            await send_deadline_list(ctx, deadlines, "All MIT Deadlines")
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
                await ctx.respond(embed=embed)
        else:
            # Fallback to keyword search
            results = await db_manager.search_deadlines(query)
            if not results:
                await ctx.respond(f"No deadlines found for '{query}'. Try '/tim help' for examples.")
                return
            await send_smart_deadline_list(ctx, results, f"🔍 Search Results for '{query}'")
    
    await safe_defer_and_respond(ctx, execute)

# Quick access command for immediate deadlines (moved from simplified_interface)
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
            await ctx.respond(embed=embed)
            return
        
        await send_smart_deadline_list(ctx, deadlines, "🚨 Urgent Deadlines (Next 3 Days)")
    
    await safe_defer_and_respond(ctx, execute)

# One-click setup command (moved from simplified_interface)
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
                    elif days_until == 0:
                        status_circle = "🔴"  # Red for due today
                    elif days_until == 1:
                        status_circle = "🔴"  # Red for due tomorrow
                    elif days_until <= 3:
                        status_circle = "🔴"  # Red for urgent (next 3 days)
                    elif days_until <= 7:
                        status_circle = "🟠"  # Orange for this week
                    else:
                        status_circle = "🟠"  # Orange for upcoming
                    
                    full_date_time = f"{date_str} at {time_str}"
                    
                except Exception:
                    status_circle = "🟠"
                    full_date_time = "Date and time unknown"
            else:
                status_circle = "🟠"
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
    
    # Send response for single page
    if len(pages) == 1:
        await ctx.respond(embed=pages[0])
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
        name="Advanced Commands",
        value=(
            "• `/deadlines next` - Show deadlines in next X days\n"
            "• `/deadlines search` - Search for specific deadlines\n"
            "• `/deadlines remind` - Set personal reminders\n"
            "• `/timezone` - Set your timezone\n"
            "• `/preferences` - Manage notification settings\n"
        ),
        inline=False
    )
    
    embed.set_footer(text="Tim understands natural language - just ask!")
    await ctx.edit_response(embed=embed)

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
            "• Use `/timezone` to change your timezone\n"
            "• Use `/preferences` for detailed settings\n"
        ),
        inline=False
    )
    
    embed.set_footer(text="Most students use the default MIT timezone (US/Eastern)")
    await ctx.edit_response(embed=embed)

@deadlines.include
@arc.slash_subcommand("next", "Show deadlines in the next X days")
async def next_deadlines(
    ctx: arc.GatewayContext,
    days: arc.Option[int, arc.IntParams("Number of days to look ahead")] = 7
) -> None:
    """Show deadlines coming up in the next X days."""
    try:
        await ctx.defer()
        
        db_manager = ctx.client.get_type_dependency(DatabaseManager)
        
        deadlines = await db_manager.get_upcoming_deadlines(days)
        
        if not deadlines:
            await ctx.respond(f"Great news! 🎉 No deadlines in the next {days} days.")
            return
        
        await send_smart_deadline_list(ctx, deadlines, title=f"Upcoming Deadlines (Next {days} Days)")
        
    except NotFoundError as e:
        logger.error(f"Discord interaction not found: {e}")
        return
    except BadRequestError as e:
        logger.error(f"Discord interaction already acknowledged: {e}")
        return
    except Exception as e:
        logger.error(f"Error fetching upcoming deadlines: {e}")
        try:
            await ctx.respond("Sorry, something went wrong while retrieving upcoming deadlines.")
        except (NotFoundError, BadRequestError):
            pass

@deadlines.include
@arc.slash_subcommand("search", "Search for deadlines")
async def search_deadlines(
    ctx: arc.GatewayContext,
    query: arc.Option[str, arc.StrParams("Search query for deadlines")]
) -> None:
    """Search for deadlines using natural language."""
    try:
        # Defer immediately to prevent timeout
        await ctx.defer()
        
        db_manager = ctx.client.get_type_dependency(DatabaseManager)
        
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
            
            await send_smart_deadline_list(ctx, results, title=f"Search Results for '{query}'")
            
    except NotFoundError as e:
        logger.error(f"Discord interaction not found: {e}")
        # Interaction expired, can't respond
        return
    except BadRequestError as e:
        logger.error(f"Discord interaction already acknowledged: {e}")
        # Interaction already handled, can't respond again
        return
    except Exception as e:
        logger.error(f"Error searching deadlines: {e}")
        try:
            await ctx.respond("Sorry, something went wrong while searching for deadlines.")
        except (NotFoundError, BadRequestError):
            # Can't respond to expired/acknowledged interaction
            pass

@deadlines.include
@arc.slash_subcommand("remind", "Set a personal reminder for a deadline")
async def set_reminder(
    ctx: arc.GatewayContext,
    deadline_id: arc.Option[int, arc.IntParams("ID of the deadline to set a reminder for")],
    hours: arc.Option[int, arc.IntParams("Hours before deadline to be reminded")] = 24
) -> None:
    """Set a personal reminder for a deadline that will be sent via DM."""
    db_manager = ctx.client.get_type_dependency(DatabaseManager)
    
    try:
        # Check if deadline exists
        deadlines = await db_manager.get_deadlines()
        deadline = next((d for d in deadlines if d['id'] == deadline_id), None)
        
        if not deadline:
            await ctx.respond("❌ Deadline not found. Please check the ID and try again.", flags=hikari.MessageFlag.EPHEMERAL)
            return
        
        # Calculate reminder time
        due_date = datetime.fromisoformat(deadline['due_date'].replace('Z', '+00:00'))
        reminder_time = due_date - timedelta(hours=hours)
        
        # Check if reminder time is in the past
        if reminder_time <= datetime.now(timezone.utc):
            await ctx.respond("❌ The reminder time would be in the past. Please choose fewer hours or a different deadline.", flags=hikari.MessageFlag.EPHEMERAL)
            return
        
        # Store the personal reminder in database
        await db_manager.add_personal_reminder(
            user_id=ctx.author.id,
            deadline_id=deadline_id,
            reminder_time=reminder_time,
            hours_before=hours
        )
        
        # Send confirmation
        embed = hikari.Embed(
            title="✅ Personal Reminder Set",
            description=f"I'll send you a **DM** about **{deadline['title']}** {hours} hour(s) before the deadline.",
            color=0x00BFFF,
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(name="📅 Due Date", value=due_date.strftime("%B %d, %Y at %I:%M %p EST"), inline=True)
        embed.add_field(name="⏰ Reminder Time", value=reminder_time.strftime("%B %d, %Y at %I:%M %p EST"), inline=True)
        embed.add_field(name="📬 Delivery Method", value="Direct Message (DM)", inline=True)
        
        embed.add_field(
            name="💡 Note", 
            value="Make sure your DMs are open so I can reach you!", 
            inline=False
        )
        
        embed.set_footer(text="Sir Tim the Timely • Personal Reminder System")
        
        await ctx.respond(embed=embed, flags=hikari.MessageFlag.EPHEMERAL)
        
    except Exception as e:
        logger.error(f"Error setting personal reminder: {e}")
        await ctx.respond("❌ Sorry, something went wrong while setting your reminder.", flags=hikari.MessageFlag.EPHEMERAL)

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
            "• `/tim` - List all deadlines (recommended)\n"
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
            "A: Server-wide reminders are sent to configured channels 24 and 6 hours before deadlines. For personal DM reminders, use `/deadlines remind` with a deadline ID.\n\n"
            "**Q: What's the difference between `/tim` and `/deadlines` commands?**\n"
            "A: `/tim` is the main command for viewing all deadlines. Use `/deadlines` subcommands for specific tasks."
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
