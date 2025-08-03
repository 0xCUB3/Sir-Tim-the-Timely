"""
Utility Command Module for Sir Tim the Timely

Implements utility commands for user settings and preferences.
"""

import logging
import functools
import hikari
import arc
from hikari.errors import NotFoundError, BadRequestError
from datetime import datetime
import pytz
from ..database import DatabaseManager

logger = logging.getLogger("sir_tim.commands.utils")

def safe_command(func):
    """Decorator to defer interaction and handle errors uniformly."""
    @functools.wraps(func)
    async def wrapper(ctx: arc.GatewayContext, *args, **kwargs):
        try:
            await ctx.defer()
            return await func(ctx, *args, **kwargs)
        except NotFoundError:
            logger.error("Discord interaction not found")
        except BadRequestError:
            logger.error("Discord interaction already acknowledged")
        except Exception as e:
            logger.error(f"Error in command {func.__name__}: {e}")
            try:
                await ctx.respond("Sorry, something went wrong.")
            except Exception:
                pass
    return wrapper

# Create a plugin for utility commands
plugin = arc.GatewayPlugin("utils")

# Define utility commands directly without a group
@plugin.include
@arc.slash_command("timezone", "Set your preferred timezone")
async def set_timezone(ctx: arc.GatewayContext) -> None:
    """Set your preferred timezone for deadlines and reminders."""
    db_manager = ctx.client.get_type_dependency(DatabaseManager)
    
    # In a real implementation this would be a choice option
    timezone_str = "US/Eastern"  # Default
    
    try:
        # Validate timezone
        try:
            tz = pytz.timezone(timezone_str)
        except pytz.exceptions.UnknownTimeZoneError:
            await ctx.respond(f"❌ Invalid timezone: {timezone_str}\nPlease use a valid timezone identifier.")
            return
        
        # Update user preferences
        await db_manager.update_user_preferences(
            user_id=ctx.author.id,
            timezone=timezone_str
        )
        
        # Get current time in selected timezone
        now = datetime.now(tz)
        
        embed = hikari.Embed(
            title="⏰ Timezone Set",
            description=f"Your timezone has been set to **{timezone_str}**.",
            color=0x00BFFF,
            timestamp=datetime.now(pytz.UTC)
        )
        
        embed.add_field(
            name="Current Time (Your Timezone)",
            value=now.strftime("%I:%M %p, %B %d, %Y"),
            inline=False
        )
        
        embed.set_footer(text="Sir Tim the Timely • User Settings")
        
        await ctx.respond(embed=embed)
        
    except Exception as e:
        logger.error(f"Error setting timezone: {e}")
        await ctx.respond("❌ Failed to update your timezone settings.")

@plugin.include
@arc.slash_command("preferences", "Configure your reminder and notification preferences")
async def manage_preferences(ctx: arc.GatewayContext) -> None:
    """Configure reminder and notification preferences."""
    db_manager = ctx.client.get_type_dependency(DatabaseManager)
    
    # In a real implementation these would be options
    daily_reminder_time = "09:00"  # Default
    reminders_enabled = True  # Default
    
    try:
        # Update preferences
        await db_manager.update_user_preferences(
            user_id=ctx.author.id,
            daily_reminder_time=daily_reminder_time,
            reminder_enabled=reminders_enabled
        )
        
        # Get current preferences after update
        prefs = await db_manager.get_user_preferences(ctx.author.id)
        
        embed = hikari.Embed(
            title="⚙️ Preference Settings Updated",
            description="Your notification preferences have been updated.",
            color=0x00BFFF,
            timestamp=datetime.now(pytz.UTC)
        )
        
        embed.add_field(
            name="Reminder Settings",
            value=(
                f"• Daily Reminder Time: **{prefs.get('daily_reminder_time', 'Unknown')}**\n"
                f"• Reminders Enabled: **{'Yes' if prefs.get('reminder_enabled', True) else 'No'}**\n"
                f"• Timezone: **{prefs.get('timezone', 'US/Eastern')}**\n"
            ),
            inline=False
        )
        
        embed.set_footer(text="Sir Tim the Timely • User Settings")
        
        await ctx.respond(embed=embed)
        
    except Exception as e:
        logger.error(f"Error updating preferences: {e}")
        await ctx.respond("❌ Failed to update your preferences.")

@plugin.include
@arc.slash_command("about", "Show information about Sir Tim the Timely")
async def about_bot(ctx: arc.GatewayContext) -> None:
    """Show information about the bot."""
    embed = hikari.Embed(
        title="🎓 About Sir Tim the Timely",
        description=(
            "Sir Tim is a helpful bot designed to keep MIT first-year students "
            "informed about critical deadlines and orientation tasks."
        ),
        color=0x9B59B6,
        timestamp=datetime.now(pytz.UTC)
    )
    
    embed.add_field(
        name="Features",
        value=(
            "• Automatic deadline tracking for MIT first-years\n"
            "• Daily deadline reminders\n"
            "• Natural language deadline queries\n"
            "• Personalized deadline management\n"
            "• Timezone support for accurate deadline times\n"
        ),
        inline=False
    )
    
    embed.add_field(
        name="Commands",
        value=(
            "• `/deadlines list` - View all deadlines\n"
            "• `/deadlines search` - Search for specific deadlines\n"
            "• `/deadlines next` - See upcoming deadlines\n"
            "• `/timezone` - Set your personal timezone\n"
            "• `/preferences` - Configure reminder settings\n"
            "• `/about` - Show this information\n"
        ),
        inline=False
    )
    
    embed.add_field(
        name="About",
        value=(
            "Sir Tim the Timely was created to help MIT students stay on top of "
            "important deadlines during the hectic summer before freshman year.\n\n"
            "Data is sourced directly from MIT's first-year website and updated regularly."
        ),
        inline=False
    )
    
    embed.set_footer(text="Sir Tim the Timely v1.0 • Created with ❤️ for MIT 2029")
    
    await ctx.respond(embed=embed)

@arc.loader
def load(client: arc.GatewayClient) -> None:
    """Load the plugin."""
    client.add_plugin(plugin)

@arc.unloader
def unload(client: arc.GatewayClient) -> None:
    """Unload the plugin."""
    client.remove_plugin(plugin)
