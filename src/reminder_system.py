"""
Reminder System for Sir Tim the Timely

Handles automated reminders and notifications for deadlines.
"""

import logging
import asyncio
import os
import random
from datetime import datetime, timezone
from typing import List, Dict, Set, Any
import pytz

import hikari

from .database import DatabaseManager
from .ai_handler import AIHandler

logger = logging.getLogger("sir_tim.reminder")

class ReminderSystem:
    """Manages automated deadline reminders."""
    
    def __init__(self, bot: hikari.GatewayBot, db_manager: DatabaseManager, ai_handler: AIHandler = None):
        self.bot = bot
        self.db_manager = db_manager
        self.ai_handler = ai_handler
        
        # Configuration
        self.default_timezone = pytz.timezone(os.getenv("DEFAULT_TIMEZONE", "US/Eastern"))
        self.daily_reminder_time = os.getenv("DAILY_REMINDER_TIME", "09:00")
        self.urgent_reminder_hours = [24, 6]  # Simplified to 24hr and 6hr reminders
        self.weekly_digest_time = os.getenv("WEEKLY_DIGEST_TIME", "09:00")  # Sunday morning
        self.reminder_role_id = os.getenv("REMINDER_ROLE_ID", None)  # Role to ping
        
        # State
        self.reminder_channels: Dict[int, int] = {}  # guild_id -> channel_id
        self.last_daily_reminder = None
        self.last_weekly_digest = None
        self.sent_urgent_reminders: Set[str] = set()  # deadline_id:hours combination
        
        logger.info("Reminder system initialized with simplified settings")
    
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
        # Always use timezone-aware datetime
        now = datetime.now(self.default_timezone)
        
        # Check for weekly digest (Sunday morning)
        if self._should_send_weekly_digest(now):
            await self._send_weekly_digest()
            self.last_weekly_digest = now.date()
        
        # Check for urgent reminders
        await self._send_urgent_reminders(now)
    
    def _should_send_weekly_digest(self, now: datetime) -> bool:
        """Check if it's time for the weekly digest (Sunday morning)."""
        if self.last_weekly_digest == now.date():
            return False
        
        # Only send on Sundays
        if now.weekday() != 6:  # 6 = Sunday
            return False
        
        # Parse the digest time
        try:
            digest_hour, digest_minute = map(int, self.weekly_digest_time.split(":"))
            digest_time = now.replace(hour=digest_hour, minute=digest_minute, second=0, microsecond=0)
            
            # Send if current time is past the digest time and we haven't sent today
            return now >= digest_time
        except ValueError:
            logger.warning(f"Invalid weekly digest time format: {self.weekly_digest_time}")
            return False
    
    async def _send_weekly_digest(self):
        """Send weekly digest to all configured channels."""
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

            # Check if we have any content for the digest
            upcoming_items_8_days = await self.db_manager.get_upcoming_deadlines(8)
            has_content = len(upcoming_items_8_days) > 0
            
            if has_content:
                # Build formatted message
                message = self._create_weekly_digest_message(urgent, coming_up, event_texts)
                
                # Prepare content with role ping if configured
                content = f"<@&{self.reminder_role_id}>\n# Weekly Digest\n\n{message}" if self.reminder_role_id else f"# Weekly Digest\n\n{message}"
                
                await self._broadcast_reminder(None, content)
                logger.info(f"Sent weekly digest: {len(urgent)} urgent, {len(coming_up)} upcoming, {len(event_texts)} events")
            else:
                # Send empty digest with MIT story (no role ping)
                story = await self._get_mit_story()
                message = f"# Weekly Digest\n\nGood news! No deadlines this week!\n\n{story}\n\n## Weekly Motivation\n> {self._get_funny_motivational_quote()}"
                
                await self._broadcast_reminder(None, message)
                logger.info("Sent empty weekly digest with MIT story")
        except Exception as e:
            logger.error(f"Error sending weekly digest: {e}")
    
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
                # Convert due_date to the same timezone as now for comparison
                due_date_local = due_date.astimezone(self.default_timezone)
                hours_until = (due_date_local - now).total_seconds() / 3600
                
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
                timestamp=datetime.now(timezone.utc)
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
            
            # Prepare content with role ping if configured
            content = f"⚠️ {time_text} until deadline!"
            if self.reminder_role_id:
                content = f"<@&{self.reminder_role_id}> {content}"
            
            await self._broadcast_reminder(embed, content)
            
            logger.info(f"Sent urgent reminder for deadline {deadline['id']} ({hours}h)")
            
        except Exception as e:
            logger.error(f"Error sending urgent reminder for deadline {deadline['id']}: {e}")
    
    def _create_weekly_digest_message(self, urgent: List[Dict], coming_up: List[Dict], event_texts: List[str]) -> str:
        """Create the weekly digest message."""
        message_parts = []
        
        if urgent:
            message_parts.append("## Urgent Deadlines")
            for deadline in urgent[:5]:  # Limit to 5 items
                due_date = datetime.fromisoformat(deadline['due_date'].replace('Z', '+00:00'))
                days_until = (due_date.date() - datetime.now(self.default_timezone).date()).days
                
                if days_until == 0:
                    date_text = f"**TODAY** ({due_date.strftime('%B %d')})"
                elif days_until == 1:
                    date_text = f"**Tomorrow** ({due_date.strftime('%B %d')})"
                else:
                    date_text = f"**{due_date.strftime('%B %d')}**"
                
                message_parts.append(f"- {deadline['title']} - {date_text}")
            message_parts.append("")
        
        if coming_up:
            message_parts.append("## Coming Up This Week")
            for deadline in coming_up[:8]:  # Limit to 8 items
                due_date = datetime.fromisoformat(deadline['due_date'].replace('Z', '+00:00'))
                message_parts.append(f"- {deadline['title']} - {due_date.strftime('%B %d')}")
            message_parts.append("")
        
        if event_texts:
            message_parts.append("## Upcoming Events")
            for event in event_texts:
                # Remove emoji from event text
                clean_event = event.replace("• **", "- **").replace("•", "-")
                message_parts.append(clean_event)
            message_parts.append("")
        
        message_parts.append("### Weekly Motivation")
        message_parts.append(f"-# {self._get_funny_motivational_quote()}")
        
        return "\n".join(message_parts)
    
    async def _get_mit_story(self) -> str:
        """Get a convoluted MIT story using AI if available, otherwise use a fallback."""
        if self.ai_handler:
            try:
                prompt = """You are Sir Tim the Timely, a sophisticated MIT deadline bot with a quirky personality. Write a short, convoluted story (2-3 sentences) about your fictional MIT life experiences. Make it humorous and relate it to having no deadlines this week. Include MIT-specific references like dorms, classes, or campus life. Keep it under 150 words and make it entertaining."""
                
                story = await self.ai_handler.process_query(prompt, [])
                return f"## Sir Tim's MIT Adventures\n{story}"
            except Exception as e:
                logger.warning(f"Failed to generate MIT story with AI: {e}")
        
        # Fallback stories if AI is not available
        fallback_stories = [
            "## Sir Tim's MIT Adventures\nI tried to calculate the probability of having no deadlines this week, but my calculator exploded from the sheer impossibility. Turns out even MIT math can't handle miracles!",
            "## Sir Tim's MIT Adventures\nI was so shocked by the lack of deadlines that I accidentally submitted my grocery list to Course 6. Professor said it was still more organized than most problem sets.",
            "## Sir Tim's MIT Adventures\nWith no deadlines this week, I finally had time to debug my own code. Found 47 errors and a recursive loop that's been running since 1999. Still better than pset deadlines!",
            "## Sir Tim's MIT Adventures\nI celebrated the deadline-free week by trying to solve the Infinite Corridor mystery. Got lost for 3 hours and somehow ended up in Building 32. Still counts as a win!",
            "## Sir Tim's MIT Adventures\nNo deadlines means I can finally attend those 'optional' lectures. Discovered they're actually mandatory. Classic MIT plot twist!"
        ]
        return random.choice(fallback_stories)
    
    def _get_funny_motivational_quote(self) -> str:
        """Get a random motivational quote."""
        quotes = [
            "Procrastination is like a credit card: it's a lot of fun until you get the bill. - Christopher Parker",
            "The way to get started is to quit talking and begin doing. - Walt Disney",
            "Success is not final, failure is not fatal: it is the courage to continue that counts. - Winston Churchill",
            "It does not matter how slowly you go as long as you do not stop. - Confucius",
            "Everything you've ever wanted is on the other side of fear. - George Addair",
            "Believe you can and you're halfway there. - Theodore Roosevelt",
            "The future depends on what you do today. - Mahatma Gandhi",
            "Don't watch the clock; do what it does. Keep going. - Sam Levenson",
            "The only way to do great work is to love what you do. - Steve Jobs",
            "Life is what happens when you're busy making other plans. - John Lennon",
            "The future belongs to those who believe in the beauty of their dreams. - Eleanor Roosevelt",
            "Be yourself; everyone else is already taken. - Oscar Wilde",
            "Two things are infinite: the universe and human stupidity; and I'm not sure about the universe. - Albert Einstein",
            "In the end, we will remember not the words of our enemies, but the silence of our friends. - Martin Luther King Jr.",
            "I have not failed. I've just found 10,000 ways that won't work. - Thomas Edison",
            "Whether you think you can or you think you can't, you're right. - Henry Ford",
            "I can resist everything except temptation. - Oscar Wilde",
            "You miss 100% of the shots you don't take. - Wayne Gretzky",
            "The only impossible journey is the one you never begin. - Tony Robbins",
            "Don't be afraid to give up the good to go for the great. - John D. Rockefeller",
            "The pessimist sees difficulty in every opportunity. The optimist sees opportunity in every difficulty. - Winston Churchill",
            "It is better to fail in originality than to succeed in imitation. - Herman Melville",
            "The road to success and the road to failure are almost exactly the same. - Colin R. Davis",
            "Success is walking from failure to failure with no loss of enthusiasm. - Winston Churchill",
            "Don't let yesterday take up too much of today. - Will Rogers",
            "You learn more from failure than from success. Don't let it stop you. Failure builds character. - Unknown",
            "If you are not willing to risk the usual, you will have to settle for the ordinary. - Jim Rohn",
            "All our dreams can come true if we have the courage to pursue them. - Walt Disney",
            "Innovation distinguishes between a leader and a follower. - Steve Jobs",
            "If you want to achieve greatness stop asking for permission. - Anonymous",
            "The successful warrior is the average man with laser-like focus. - Bruce Lee",
            "Take up one idea. Make that one idea your life—think of it, dream of it, live on that idea. - Swami Vivekananda",
            "You are never too old to set another goal or to dream a new dream. - C.S. Lewis",
            "The only person you are destined to become is the person you decide to be. - Ralph Waldo Emerson",
            "Go confidently in the direction of your dreams. Live the life you have imagined. - Henry David Thoreau",
            "Twenty years from now you will be more disappointed by the things that you didn't do than by the ones you did do. - Mark Twain",
            "A person who never made a mistake never tried anything new. - Albert Einstein",
            "The mind is everything. What you think you become. - Buddha",
            "Strive not to be a success, but rather to be of value. - Albert Einstein",
            "I attribute my success to this: I never gave or took any excuse. - Florence Nightingale",
            "The most difficult thing is the decision to act, the rest is merely tenacity. - Amelia Earhart",
            "Every strike brings me closer to the next home run. - Babe Ruth",
            "Success is not the key to happiness. Happiness is the key to success. If you love what you are doing, you will be successful. - Albert Schweitzer",
            "The best time to plant a tree was 20 years ago. The second best time is now. - Chinese Proverb",
            "If you want to live a happy life, tie it to a goal, not to people or things. - Albert Einstein",
            "The difference between ordinary and extraordinary is that little extra. - Jimmy Johnson",
            "Success is the sum of small efforts, repeated day in and day out. - Robert Collier",
            "Don't be pushed around by the fears in your mind. Be led by the dreams in your heart. - Roy T. Bennett",
            "The only limit to our realization of tomorrow will be our doubts of today. - Franklin D. Roosevelt",
            "What lies behind us and what lies before us are tiny matters compared to what lies within us. - Ralph Waldo Emerson",
            "You have been assigned this mountain to show others it can be moved. - Mel Robbins",
            "The way I see it, if you want the rainbow, you gotta put up with the rain. - Dolly Parton",
            "Champions don't become champions in the ring. They become champions in their training. - Muhammad Ali",
            "You don't have to be great to get started, but you have to get started to be great. - Zig Ziglar",
            "The expert in anything was once a beginner. - Helen Hayes",
            "Success is not how high you have climbed, but how you make a positive difference to the world. - Roy T. Bennett",
            "Don't let what you cannot do interfere with what you can do. - John Wooden",
            "The beautiful thing about learning is that nobody can take it away from you. - B.B. King",
            "A goal is a dream with a deadline. - Napoleon Hill",
            "The secret of getting ahead is getting started. - Mark Twain",
            "It is never too late to be what you might have been. - George Eliot",
            "The only thing standing between you and your goal is the story you keep telling yourself as to why you can't achieve it. - Jordan Belfort",
            "If you're going through hell, keep going. - Winston Churchill",
            "The greatest glory in living lies not in never falling, but in rising every time we fall. - Nelson Mandela"
        ]
        return random.choice(quotes)
    
    async def _broadcast_reminder(self, embed: hikari.Embed = None, content: str = ""):
        """Broadcast a reminder to all configured channels."""
        sent_count = 0
        
        for guild_id, channel_id in self.reminder_channels.items():
            try:
                if embed:
                    await self.bot.rest.create_message(
                        channel_id,
                        content=content,
                        embed=embed
                    )
                else:
                    await self.bot.rest.create_message(
                        channel_id,
                        content=content
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
        """Send a test reminder using the next actual deadline."""
        try:
            # Get the next upcoming deadline
            upcoming_deadlines = await self.db_manager.get_upcoming_deadlines(30)
            
            if not upcoming_deadlines:
                # No deadlines found, send a basic test
                embed = hikari.Embed(
                    title="Test Reminder",
                    description="No upcoming deadlines found to test with.",
                    color=0x00FF00,
                    timestamp=datetime.now(timezone.utc)
                )
                embed.add_field(
                    name="Status",
                    value="Reminder system is working, but no deadlines in next 30 days",
                    inline=False
                )
                embed.set_footer(text="Sir Tim the Timely • Test Reminder")
                
                # Prepare content with role ping if configured
                content = "🧪 Test Reminder (No upcoming deadlines)"
                if self.reminder_role_id:
                    content = f"<@&{self.reminder_role_id}> {content}"
                
                await self.bot.rest.create_message(
                    channel_id,
                    content=content,
                    embed=embed
                )
                return True
            
            # Use the first deadline for testing
            deadline = upcoming_deadlines[0]
            due_date = datetime.fromisoformat(deadline['due_date'].replace('Z', '+00:00'))
            
            # Create Discord timestamp
            discord_timestamp = f"<t:{int(due_date.timestamp())}:R>"
            
            embed = hikari.Embed(
                title="Test Reminder",
                description=f"**{deadline['title']}** is due {discord_timestamp}",
                color=0xFF6B35,
                timestamp=datetime.now(timezone.utc)
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
                    description = description[:200] + "..."
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
            
            embed.set_footer(text="Sir Tim the Timely • Test Reminder")
            
            # Prepare content with role ping if configured
            content = "🧪 Test Reminder"
            if self.reminder_role_id:
                content = f"<@&{self.reminder_role_id}> {content}"
            
            await self.bot.rest.create_message(
                channel_id,
                content=content,
                embed=embed
            )
            
            logger.info(f"Sent test reminder for deadline {deadline['id']} to channel {channel_id}")
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
