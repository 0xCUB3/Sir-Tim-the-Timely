"""
Reminder System for Sir Tim the Timely

Handles automated reminders and notifications for deadlines.
"""

import logging
import asyncio
import os
from datetime import datetime
from typing import List, Dict, Set, Any
import pytz

import hikari

from .database import DatabaseManager

logger = logging.getLogger("sir_tim.reminder")

class ReminderSystem:
    """Manages automated deadline reminders."""
    
    def __init__(self, bot: hikari.GatewayBot, db_manager: DatabaseManager):
        self.bot = bot
        self.db_manager = db_manager
        
        # Configuration
        self.default_timezone = pytz.timezone(os.getenv("DEFAULT_TIMEZONE", "US/Eastern"))
        self.daily_reminder_time = os.getenv("DAILY_REMINDER_TIME", "09:00")
        self.urgent_reminder_hours = [int(h) for h in os.getenv("URGENT_REMINDER_HOURS", "24,12,6").split(",")]
        
        # State
        self.reminder_channels: Dict[int, int] = {}  # guild_id -> channel_id
        self.last_daily_reminder = None
        self.sent_urgent_reminders: Set[str] = set()  # deadline_id:hours combination
        
        logger.info("Reminder system initialized")
    
    async def start_reminder_loop(self):
        """Start the main reminder loop."""
        while True:
            try:
                await self._check_and_send_reminders()
                
                # Sleep for 1 hour between checks
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in reminder loop: {e}")
                await asyncio.sleep(3600)
    
    async def _check_and_send_reminders(self):
        """Check for due reminders and send them."""
        now = datetime.now(self.default_timezone)
        
        # Check for daily reminders
        if self._should_send_daily_reminder(now):
            await self._send_daily_reminders()
            self.last_daily_reminder = now.date()
        
        # Check for urgent reminders
        await self._send_urgent_reminders(now)
    
    def _should_send_daily_reminder(self, now: datetime) -> bool:
        """Check if it's time for the daily reminder."""
        if self.last_daily_reminder == now.date():
            return False
        
        # Parse the reminder time
        try:
            reminder_hour, reminder_minute = map(int, self.daily_reminder_time.split(":"))
            reminder_time = now.replace(hour=reminder_hour, minute=reminder_minute, second=0, microsecond=0)
            
            # Send if current time is past the reminder time and we haven't sent today
            return now >= reminder_time
            
        except ValueError:
            logger.warning(f"Invalid daily reminder time format: {self.daily_reminder_time}")
            return False
    
    async def _send_daily_reminders(self):
        """Send daily deadline reminders to all configured channels."""
        try:
            # Get upcoming items for the next 7 days
            upcoming_items = await self.db_manager.get_upcoming_deadlines(7)
            # Separate deadlines and events
            upcoming_deadlines = [item for item in upcoming_items if not item.get('is_event')]
            upcoming_events = [item for item in upcoming_items if item.get('is_event')]
            if not upcoming_deadlines and not upcoming_events:
                return

            # Group deadlines by urgency and collect event texts
            today = datetime.now(self.default_timezone).date()
            urgent: List[Dict] = []       # Due within 2 days
            coming_up: List[Dict] = []    # Due within 7 days
            event_texts: List[str] = []

            # Process deadlines
            for deadline in upcoming_deadlines:
                due = datetime.fromisoformat(deadline['due_date'].replace('Z', '+00:00')).date()
                days_until = (due - today).days
                if days_until <= 2:
                    urgent.append(deadline)
                else:
                    coming_up.append(deadline)

            # Process events
            for event in upcoming_events:
                # Parse start and end dates
                start = None
                if event.get('start_date'):
                    start = datetime.fromisoformat(event['start_date'].replace('Z', '+00:00')).date()
                end = datetime.fromisoformat(event['due_date'].replace('Z', '+00:00')).date()
                # Format event message
                if start:
                    if start == today:
                        event_texts.append(
                            f"• **{event['title']}** starts today and runs until {end.strftime('%B %d')}"
                        )
                    else:
                        days_start = (start - today).days
                        event_texts.append(
                            f"• **{event['title']}** starts in {days_start} day{'s' if days_start != 1 else ''} (until {end.strftime('%B %d')})"
                        )
                else:
                    event_texts.append(
                        f"• **{event['title']}** happening until {end.strftime('%B %d')}"
                    )

            # Build and broadcast embed
            embed = self._create_daily_reminder_embed(urgent, coming_up)
            if event_texts:
                embed.add_field(
                    name="🎉 Upcoming Events",
                    value="\n".join(event_texts),
                    inline=False
                )
            await self._broadcast_reminder(embed, "📅 Daily Deadline Reminder")
            logger.info(f"Sent daily reminders: {len(urgent)} urgent, {len(coming_up)} upcoming, {len(event_texts)} events")
        except Exception as e:
            logger.error(f"Error sending daily reminders: {e}")
    
    async def _send_urgent_reminders(self, now: datetime):
        """Send urgent reminders for deadlines approaching critical hours."""
        try:
            # Get deadlines for the next 48 hours
            upcoming_deadlines = await self.db_manager.get_upcoming_deadlines(2)
             
            for deadline in upcoming_deadlines:
                # skip events for urgent reminders
                if deadline.get('is_event'):
                    continue
                due_date = datetime.fromisoformat(deadline['due_date'].replace('Z', '+00:00'))
                hours_until = (due_date - now).total_seconds() / 3600
                
                # Check if we should send an urgent reminder
                for threshold_hours in self.urgent_reminder_hours:
                    reminder_key = f"{deadline['id']}:{threshold_hours}"
                    
                    if (hours_until <= threshold_hours and 
                        hours_until > threshold_hours - 1 and  # Within the last hour of threshold
                        reminder_key not in self.sent_urgent_reminders):
                        
                        await self._send_urgent_reminder(deadline, threshold_hours)
                        self.sent_urgent_reminders.add(reminder_key)
                        
                        # Clean up old reminder tracking (keep only last 7 days)
                        if len(self.sent_urgent_reminders) > 1000:
                            self.sent_urgent_reminders.clear()
                        
        except Exception as e:
            logger.error(f"Error sending urgent reminders: {e}")
    
    async def _send_urgent_reminder(self, deadline: Dict, hours: int):
        """Send an urgent reminder for a specific deadline."""
        try:
            time_text = f"{hours} hour{'s' if hours != 1 else ''}"
            
            embed = hikari.Embed(
                title="🚨 Urgent Deadline Alert!",
                description=f"**{deadline['title']}** is due in {time_text}!",
                color=0xFF4444 if hours <= 6 else 0xFF8800,
                timestamp=datetime.now().astimezone()
            )
            
            due_date = datetime.fromisoformat(deadline['due_date'].replace('Z', '+00:00'))
            embed.add_field(
                name="Due Date",
                value=due_date.strftime("%B %d, %Y at %I:%M %p"),
                inline=True
            )
            
            if deadline.get('category'):
                embed.add_field(
                    name="Category",
                    value=deadline['category'],
                    inline=True
                )
            
            if deadline.get('description'):
                description = deadline['description']
                if len(description) > 200:
                    description = description[:197] + "..."
                embed.add_field(
                    name="Details",
                    value=description,
                    inline=False
                )
            
            if deadline.get('url'):
                embed.add_field(
                    name="Link",
                    value=f"[More Information]({deadline['url']})",
                    inline=True
                )
            
            embed.set_footer(text="Sir Tim the Timely • MIT Deadline Bot")
            
            await self._broadcast_reminder(embed, f"⚠️ {time_text} until deadline!")
            
            logger.info(f"Sent urgent reminder for deadline {deadline['id']} ({hours}h)")
            
        except Exception as e:
            logger.error(f"Error sending urgent reminder for deadline {deadline['id']}: {e}")
    
    def _create_daily_reminder_embed(self, urgent: List[Dict], coming_up: List[Dict]) -> hikari.Embed:
        """Create the daily reminder embed."""
        embed = hikari.Embed(
            title="📅 Daily Deadline Reminder",
            description="Here's what's coming up for MIT Class of 2029:",
            color=0x4285F4,
            timestamp=datetime.now().astimezone()
        )
        
        if urgent:
            urgent_text = []
            for deadline in urgent[:5]:  # Limit to 5 items
                due_date = datetime.fromisoformat(deadline['due_date'].replace('Z', '+00:00'))
                days_until = (due_date.date() - datetime.now(self.default_timezone).date()).days
                
                if days_until == 0:
                    time_text = "**TODAY**"
                elif days_until == 1:
                    time_text = "**Tomorrow**"
                else:
                    time_text = f"**{days_until} days**"
                
                urgent_text.append(f"• {deadline['title']} - {time_text}")
            
            embed.add_field(
                name="🚨 Urgent (Due Soon)",
                value="\n".join(urgent_text),
                inline=False
            )
        
        if coming_up:
            coming_text = []
            for deadline in coming_up[:8]:  # Limit to 8 items
                due_date = datetime.fromisoformat(deadline['due_date'].replace('Z', '+00:00'))
                coming_text.append(f"• {deadline['title']} - {due_date.strftime('%B %d')}")
            
            embed.add_field(
                name="📋 Coming Up This Week",
                value="\n".join(coming_text),
                inline=False
            )
        
        embed.add_field(
            name="💡 Tip",
            value="Use `/deadlines next` to see detailed information about upcoming deadlines, or `/deadlines help` for all available commands.",
            inline=False
        )
        
        embed.set_footer(text="Sir Tim the Timely • MIT Deadline Bot")
        
        return embed
    
    async def _broadcast_reminder(self, embed: hikari.Embed, content: str = ""):
        """Broadcast a reminder to all configured channels."""
        sent_count = 0
        
        for guild_id, channel_id in self.reminder_channels.items():
            try:
                await self.bot.rest.create_message(
                    channel_id,
                    content=content,
                    embed=embed
                )
                sent_count += 1
                
            except hikari.ForbiddenError:
                logger.warning(f"No permission to send message in channel {channel_id}")
            except hikari.NotFoundError:
                logger.warning(f"Channel {channel_id} not found, removing from reminders")
                del self.reminder_channels[guild_id]
            except Exception as e:
                logger.error(f"Error sending reminder to channel {channel_id}: {e}")
        
        logger.info(f"Broadcast reminder sent to {sent_count} channels")
    
    async def set_reminder_channel(self, guild_id: int, channel_id: int):
        """Set the reminder channel for a guild."""
        self.reminder_channels[guild_id] = channel_id
        
        # TODO: Store in database for persistence
        logger.info(f"Set reminder channel for guild {guild_id} to channel {channel_id}")
    
    async def remove_reminder_channel(self, guild_id: int):
        """Remove the reminder channel for a guild."""
        if guild_id in self.reminder_channels:
            del self.reminder_channels[guild_id]
            logger.info(f"Removed reminder channel for guild {guild_id}")
    
    async def send_test_reminder(self, channel_id: int):
        """Send a test reminder to a specific channel."""
        try:
            embed = hikari.Embed(
                title="🧪 Test Reminder",
                description="This is a test of the Sir Tim reminder system!",
                color=0x00FF00,
                timestamp=datetime.now().astimezone()
            )
            
            embed.add_field(
                name="Status",
                value="✅ Reminder system is working correctly",
                inline=True
            )
            
            embed.set_footer(text="Sir Tim the Timely • Test Reminder")
            
            await self.bot.rest.create_message(
                channel_id,
                content="🔔 Test Reminder",
                embed=embed
            )
            
            logger.info(f"Sent test reminder to channel {channel_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send test reminder: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the reminder system."""
        return {
            'configured_channels': len(self.reminder_channels),
            'last_daily_reminder': self.last_daily_reminder.isoformat() if self.last_daily_reminder else None,
            'urgent_reminders_sent': len(self.sent_urgent_reminders),
            'daily_reminder_time': self.daily_reminder_time,
            'urgent_thresholds': self.urgent_reminder_hours
        }
