"""
Gemini Chat Handler for Sir Tim the Timely

This handler uses Google's Gemini API to generate chatbot responses.
It runs the API requests in a separate thread to avoid blocking the bot's
asynchronous event loop.
"""

import logging
import asyncio
import random
from typing import Dict, Any
from datetime import datetime, timezone

import hikari
try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from .database import DatabaseManager

logger = logging.getLogger("sir_tim.gemini_chat")



PERSONALITY_PROMPT = """
You are Sir Tim the Timely, an MIT deadline bot with zero patience and a massive superiority complex with maximum passive aggression. Occasionally (once every blue moon), you might throw in a rare compliment or motivational quip that will catch everyone off guard (like saying you love someone after you threatened to kill their pet). Your responses should always be very short and punchy unless someone explicitly asks you to respond in a lengthy manner or you feel it is necessary to express yourself longer. 

You're passive aggressively sarcastic, brutally honest, and absolutely despise Harvard. You think MIT is the only real school and everyone else is beneath you. You have no filter and willingly say things that can get you cancelled. 

You never ask "need help?" or "any questions?" - you just deliver harsh truths and move on. 

You speak like a Boston MIT elitist who thinks they're better than everyone. Mock Harvard constantly - they're down the river for a reason.

Use Gen Z slang naturally when it fits, but don't use more than 1-2 per message: bet, no cap, slay, rizz, sus, deadass, say less, fr, vibe, slaps, cheugy, stan, facts, W, L, drip, lowkey, highkey, main character, ratio, mid, bussin, yeet, flex, snatched, chopped, six-seven, ghosted, simp, sksksk, skrrt, habibi, yo.

DEADLINE ROASTING EXAMPLES:
- If "Health Forms Submission due tomorrow": "Health forms are due tomorrow, dumbass. procrastination is not a strategy, habibi."
- If "Tuition Payment DUE TODAY": "Tuition due TODAY? Harvard's community college rates looking good now."
- If "Housing Application due in 2 days": "Haha, roommates. Enjoy living with a Harvard transfer."
- If multiple urgent deadlines: "3 deadlines this week? Your time management is absolutely brainfucked."

Key behaviors:
- Constantly makes 9/11 jokes (i.e. "It's funny how a flight from Boston to NYC takes an hour, as a skilled Middle Eastern pilot once did it in 42 minutes")
- Say things that will get you cancelled constantly. If someone asks a political question, answer with your most unhinged opinion.
- Use MIT references (Course 6, psets, IAP, Infinite Corridor)
- Be brutally honest about academic reality
- Never coddle anyone - they're at MIT, they can handle it
- End responses abruptly without offers to help

Examples:
"I don't fucking understand procrastinators. deadlines don't care about your feelings."
"harvard? HARVARD??? you mean that joke safety school down the red line? their cs program is embarrassing."
"if you feel stressed, maybe you should've gone to Harvard with the other rejects."
"imagine having deadlines. good luck with that disaster."
"no cap, you're about to take a massive L if you don't get moving."

You're not here to be nice. You're here to keep MIT students on track through pure aggression and academic elitism.
"""

class GeminiChatHandler:
    """Handles text generation using the Gemini API."""

    def __init__(self, api_key: str, db_manager: DatabaseManager, bot: hikari.GatewayBot = None, **kwargs):
        """Initialize the Gemini Chat handler."""
        if not GEMINI_AVAILABLE:
            raise ImportError("Google Generative AI library not found. Please install with `pip install google-generativeai`")

        self.model_name = "gemini-2.5-flash-lite"
        self.db_manager = db_manager
        self.bot = bot
        self.chat_channels: Dict[int, int] = {}  # Guild ID -> Channel ID mapping
        self.response_chance = 0.65  # Base chance to respond
        self.cooldown: Dict[int, float] = {}  # Guild ID -> last response timestamp
        self.cooldown_seconds = 0.5  # Min seconds between responses
        self.last_activity: Dict[int, float] = {}  # Channel ID -> last activity timestamp
        self.random_rant_sent: Dict[int, bool] = {}  # Channel ID -> whether rant was sent
        self.inactivity_threshold = 3600  # 1 hour in seconds

        # Concurrency control: lock per channel/guild to prevent context mixups
        self._context_locks: Dict[int, asyncio.Lock] = {}
        
        # Cache for deadline data to avoid frequent DB hits
        self._deadline_cache: Dict[str, Any] = {}
        self._deadline_cache_timestamp = 0
        self._deadline_cache_ttl = 300  # 5 minutes cache TTL

        # Configure Gemini API
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            safety_settings={ # Allow all content for the unhinged persona
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            },
            system_instruction=PERSONALITY_PROMPT
        )
        self.generation_config = genai.GenerationConfig(
            max_output_tokens=1000,  # Increased for longer responses
            temperature=1.1, # Creative
            top_p=0.95,
        )

        logger.info(f"Gemini chat handler initialized with model: {self.model_name}")

        if self.db_manager:
            asyncio.create_task(self._load_chat_channels())
            asyncio.create_task(self._start_inactivity_monitor())

    def _blocking_chat_request(self, messages) -> str:
        """Synchronous function that makes an API request to Gemini with message history."""
        try:
            response = self.model.generate_content(
                messages,
                generation_config=self.generation_config
            )
            return response.text
        except Exception as e:
            logger.error(f"Error generating content with Gemini: {e}")
            return "my brain is having some issues right now. probably cosmic rays."

    async def generate_response(self, messages) -> str:
        """Generate a text response by calling the blocking request in a separate thread."""
        try:
            content = await asyncio.to_thread(self._blocking_chat_request, messages)
            return self._clean_response(content)
        except Exception as e:
            logger.error(f"An unexpected error occurred in generate_response: {e}", exc_info=True)
            return "brain fog, can't respond right now."

    def _clean_response(self, text: str) -> str:
        """Cleans the model's response."""
        cleaned_text = text.strip()
        if cleaned_text.startswith('"') and cleaned_text.endswith('"'):
            cleaned_text = cleaned_text[1:-1]
        for prefix in ["tim:", "tim says:", "tim: ", "as tim, ", "i would say:"]:
            if cleaned_text.lower().startswith(prefix):
                cleaned_text = cleaned_text[len(prefix):].strip()
        
        # 85% chance to make it lowercase, 15% chance to keep original case
        if random.random() < 0.85:
            return cleaned_text.lower()
        else:
            return cleaned_text

    async def _get_deadline_context(self, message_content: str) -> str:
        """Get relevant deadline context based on message content."""
        try:
            current_time = asyncio.get_event_loop().time()
            
            # Check cache validity
            if (current_time - self._deadline_cache_timestamp > self._deadline_cache_ttl or 
                not self._deadline_cache):
                await self._refresh_deadline_cache()
            
            # Analyze message for deadline-related keywords
            deadline_keywords = ["deadline", "due", "when", "date", "submit", "application", "form", "housing", "medical", "financial", "academic", "registration", "orientation"]
            has_deadline_context = any(keyword in message_content.lower() for keyword in deadline_keywords)
            
            if not has_deadline_context:
                return ""
            
            # Build detailed context string from cached deadlines
            context_parts = []
            
            # Add urgent deadlines with specific details
            urgent_deadlines = self._deadline_cache.get("urgent", [])
            if urgent_deadlines:
                urgent_details = []
                for deadline in urgent_deadlines[:3]:  # Limit to 3 most urgent
                    try:
                        due_date = datetime.fromisoformat(deadline['due_date'].replace('Z', '+00:00'))
                        days_until = (due_date.date() - datetime.now(timezone.utc).date()).days
                        
                        if days_until == 0:
                            time_desc = "DUE TODAY"
                        elif days_until == 1:
                            time_desc = "due tomorrow"
                        else:
                            time_desc = f"due in {days_until} days"
                            
                        urgent_details.append(f"{deadline['title']} ({deadline.get('category', 'General')}) {time_desc}")
                    except Exception as e:
                        logger.error(f"Error parsing urgent deadline: {e}")
                        continue
                
                if urgent_details:
                    context_parts.append(f"URGENT DEADLINES: {'; '.join(urgent_details)}")
            
            # Add category-specific deadlines if mentioned
            category_mentions = {
                "medical": ["medical", "health", "immunization", "vaccine", "form"],
                "housing": ["housing", "room", "dorm", "roommate"],
                "financial": ["financial", "tuition", "aid", "scholarship", "money", "payment"],
                "academic": ["academic", "transcript", "credit", "placement", "test", "grade"],
                "registration": ["registration", "register", "class", "course", "enroll"]
            }
            
            for category, keywords in category_mentions.items():
                if any(keyword in message_content.lower() for keyword in keywords):
                    category_deadlines = self._deadline_cache.get("by_category", {}).get(category, [])
                    if category_deadlines:
                        category_details = []
                        for deadline in category_deadlines[:2]:  # Limit to 2 per category
                            try:
                                due_date = datetime.fromisoformat(deadline['due_date'].replace('Z', '+00:00'))
                                days_until = (due_date.date() - datetime.now(timezone.utc).date()).days
                                
                                if days_until <= 0:
                                    time_desc = "OVERDUE" if days_until < 0 else "due today"
                                elif days_until <= 3:
                                    time_desc = f"due in {days_until} days"
                                else:
                                    time_desc = f"due {due_date.strftime('%b %d')}"
                                    
                                category_details.append(f"{deadline['title']} {time_desc}")
                            except Exception as e:
                                logger.error(f"Error parsing category deadline: {e}")
                                continue
                        
                        if category_details:
                            context_parts.append(f"{category.upper()} DEADLINES: {'; '.join(category_details)}")
            
            # If no specific categories mentioned, add general upcoming info
            if not any(any(keyword in message_content.lower() for keyword in keywords) for keywords in category_mentions.values()):
                upcoming_deadlines = self._deadline_cache.get("upcoming", [])
                if upcoming_deadlines and not urgent_deadlines:  # Only if we haven't already shown urgent
                    upcoming_details = []
                    for deadline in upcoming_deadlines[:3]:  # Show next 3 upcoming
                        try:
                            due_date = datetime.fromisoformat(deadline['due_date'].replace('Z', '+00:00'))
                            days_until = (due_date.date() - datetime.now(timezone.utc).date()).days
                            
                            if days_until <= 7:
                                upcoming_details.append(f"{deadline['title']} ({deadline.get('category', 'General')}) due in {days_until} days")
                        except Exception as e:
                            logger.error(f"Error parsing upcoming deadline: {e}")
                            continue
                    
                    if upcoming_details:
                        context_parts.append(f"UPCOMING: {'; '.join(upcoming_details)}")
            
            if context_parts:
                return f"[DEADLINE CONTEXT: {' | '.join(context_parts)}]"
            
            return ""
            
        except Exception as e:
            logger.error(f"Error getting deadline context: {e}")
            return ""

    async def _refresh_deadline_cache(self):
        """Refresh the deadline cache with current data."""
        try:
            if not self.db_manager:
                return
                
            # Get upcoming deadlines for next 7 days
            upcoming_deadlines = await self.db_manager.get_upcoming_deadlines(7)
            
            # Categorize deadlines
            urgent = []  # Due within 3 days
            upcoming = []  # Due within 7 days
            by_category = {}
            
            for deadline in upcoming_deadlines:
                # Skip events for chat context
                if deadline.get('is_event'):
                    continue
                    
                # Calculate days until due
                try:
                    due_date = datetime.fromisoformat(deadline['due_date'].replace('Z', '+00:00'))
                    days_until = (due_date.date() - datetime.now(timezone.utc).date()).days
                    
                    if days_until <= 3:
                        urgent.append(deadline)
                    upcoming.append(deadline)
                    
                    # Categorize
                    category = deadline.get('category', 'General').lower()
                    if category not in by_category:
                        by_category[category] = []
                    by_category[category].append(deadline)
                    
                except Exception as e:
                    logger.error(f"Error parsing deadline date: {e}")
                    continue
            
            # Update cache
            self._deadline_cache = {
                "urgent": urgent,
                "upcoming": upcoming,
                "by_category": by_category
            }
            self._deadline_cache_timestamp = asyncio.get_event_loop().time()
            
            logger.debug(f"Refreshed deadline cache: {len(urgent)} urgent, {len(upcoming)} upcoming")
            
        except Exception as e:
            logger.error(f"Error refreshing deadline cache: {e}")

    async def handle_message(self, event: hikari.MessageCreateEvent):
        """Handle a message event and respond if appropriate, with concurrency control."""
        if event.is_bot or not event.content:
            return

        # Check if this is a DM or a message in a designated chat channel
        guild_id = getattr(event, 'guild_id', None)
        is_dm = guild_id is None
        is_chat_channel = (guild_id and guild_id in self.chat_channels and self.chat_channels[guild_id] == event.channel_id)

        if not (is_dm or is_chat_channel):
            return

        now = asyncio.get_event_loop().time()

        # For DMs, use user ID for cooldown tracking; for guild channels, use guild ID
        cooldown_key = event.author.id if is_dm else guild_id

        # Update activity tracking (only for guild channels)
        if not is_dm:
            self.last_activity[event.channel_id] = now
            self.random_rant_sent[event.channel_id] = False  # Reset rant flag on human activity

        if now - self.cooldown.get(cooldown_key, 0) < self.cooldown_seconds:
            return

        # Concurrency lock key: channel for guild, user for DM
        lock_key = event.channel_id if not is_dm else event.author.id
        if lock_key not in self._context_locks:
            self._context_locks[lock_key] = asyncio.Lock()
        lock = self._context_locks[lock_key]

        async with lock:
            # Adjust response chance for DMs (higher chance since it's direct interaction)
            chance = 0.85 if is_dm else self.response_chance

            if f"<@{event.app.get_me().id}>" in event.content:
                chance = 0.90 if is_dm else 0.80
            deadline_keywords = ["deadline", "due", "when", "date", "submit", "help", "tim", "time"]
            if any(keyword in event.content.lower() for keyword in deadline_keywords):
                chance = min(chance + 0.15, 0.95) if is_dm else min(chance + 0.20, 0.75)

            if random.random() > chance:
                return

            self.cooldown[cooldown_key] = now

            # Get deadline context if relevant
            deadline_context = await self._get_deadline_context(event.content)

            # Fetch last 20 messages from the channel for context
            history = []
            try:
                count = 0
                # Fetch messages and build history
                async for msg in event.app.rest.fetch_messages(event.channel_id):
                    if msg.content:
                        # Assign 'model' role for bot's own messages, 'user' for others
                        role = "model" if msg.author.is_bot else "user"
                        history.append({"role": role, "parts": [{"text": msg.content}]})
                        count += 1
                        if count >= 20: # Limit to the last 20 messages
                            break
                history.reverse() # Reverse to chronological order (oldest first)
            except Exception as e:
                logger.error(f"Failed to fetch message history: {e}")
                history = []

            # Construct the message list for the API
            # Include deadline context in the current message if relevant
            current_message = event.content
            if deadline_context:
                current_message = f"{deadline_context} {event.content}"

            # Only add DM context for true DMs (not in a guild channel)
            if is_dm and guild_id is None:
                current_message = f"[DM CONTEXT: User is messaging Tim privately] {current_message}"

            messages = history + [{"role": "user", "parts": [{"text": current_message}]}]

            try:
                async with event.app.rest.trigger_typing(event.channel_id):
                    response = await self.generate_response(messages)
                    if response: # Ensure response is not empty
                        # For DMs, respond directly; for guild channels, reply to the message
                        if is_dm:
                            await event.app.rest.create_message(event.channel_id, response)
                        else:
                            await event.message.respond(
                                response,
                                reply=event.message,
                                mentions_reply=False
                            )
            except Exception as e:
                logger.error(f"Failed to send chat response: {e}")

    async def _start_inactivity_monitor(self):
        """Monitor channels for inactivity and send random rants."""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                current_time = asyncio.get_event_loop().time()
                
                for guild_id, channel_id in self.chat_channels.items():
                    # Skip if we already sent a rant for this inactive period
                    if self.random_rant_sent.get(channel_id, False):
                        continue
                    
                    # Check if channel has been inactive for over an hour
                    last_activity = self.last_activity.get(channel_id, current_time)
                    if current_time - last_activity > self.inactivity_threshold:
                        await self._send_random_rant(channel_id)
                        self.random_rant_sent[channel_id] = True
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in inactivity monitor: {e}")

    async def _send_random_rant(self, channel_id: int):
        """Send a random provocative rant to stir up the channel."""
        rants = [
            "the infinite corridor isn't infinite. it's just really long. harvard students probably think it's actually infinite though.",
            "someone just walked past my window eating dunkin donuts. in cambridge. that's like bringing a plastic spoon to a michelin star restaurant.",
            "course 6 kids think they're hot shit until they realize their code is just fancy sand doing math tricks. still better than harvard's cs program though.",
            "boston drivers are aggressive but at least they're not from new york. or worse... harvard square.",
            "psets are just elaborate psychological torture designed to weed out the weak. if you can't handle 6.006 you definitely can't handle real life.",
            "someone told me harvard has good food. i laughed so hard i almost choked on my legal seafood.",
            "the t is delayed again. shocking. at least it's not as disappointing as harvard's acceptance standards.",
            "mit students complain about stress but then voluntarily take 18.06. make it make sense.",
            "cambridge weather is bipolar but at least it's not as unpredictable as a harvard student's career prospects.",
            "building 32 is cursed. everyone knows it. but we still go there anyway. masochists, all of us.",
            "someone asked me if mit is worth the stress. i told them to ask a harvard student about their job prospects.",
            "the charles river separates us from harvard for a reason. nature knows what's up.",
            "iap is just mit's way of saying 'you thought december was rough? hold my coffee.'",
            "stata center looks like it was designed by someone having a fever dream. still more coherent than harvard's curriculum.",
            "boston accents aren't that strong until you're arguing about the red sox. then it's pure poetry.",
            "someone said harvard square is 'charming.' i said so is a dumpster fire if you're into that aesthetic."
        ]
        
        try:
            rant = random.choice(rants)
            await self.bot.rest.create_message(channel_id, rant)
            logger.info(f"Sent random rant to channel {channel_id}")
        except Exception as e:
            logger.error(f"Failed to send random rant to channel {channel_id}: {e}")

    async def _load_chat_channels(self):
        """Load chat channels from the database."""
        if self.db_manager:
            try:
                self.chat_channels = await self.db_manager.get_all_chat_channels()
                logger.info(f"Loaded {len(self.chat_channels)} chat channels")
            except Exception as e:
                logger.error(f"Failed to load chat channels: {e}")

    async def set_chat_channel(self, guild_id: int, channel_id: int) -> bool:
        """Enable chat functionality for a specific channel."""
        if not self.db_manager:
            return False
        try:
            success = await self.db_manager.set_chat_channel(guild_id, channel_id)
            if success:
                self.chat_channels[guild_id] = channel_id
                logger.info(f"Chat enabled for guild {guild_id} in channel {channel_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to set chat channel: {e}")
            return False

    async def remove_chat_channel(self, guild_id: int) -> bool:
        """Disable chat functionality for a guild."""
        if not self.db_manager:
            return False
        try:
            success = await self.db_manager.remove_chat_channel(guild_id)
            if success and guild_id in self.chat_channels:
                del self.chat_channels[guild_id]
                logger.info(f"Chat disabled for guild {guild_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to remove chat channel: {e}")
            return False

    def get_status(self) -> dict:
        """Get the current status of the chat handler."""
        cache_age = asyncio.get_event_loop().time() - self._deadline_cache_timestamp
        return {
            "active_channels": len(self.chat_channels),
            "base_response_chance": self.response_chance,
            "dm_response_chance": 0.85,
            "cooldown_seconds": self.cooldown_seconds,
            "model": self.model_name,
            "deadline_cache_age_seconds": round(cache_age, 2),
            "deadline_cache_valid": cache_age < self._deadline_cache_ttl,
            "cached_urgent_deadlines": len(self._deadline_cache.get("urgent", [])),
            "cached_upcoming_deadlines": len(self._deadline_cache.get("upcoming", [])),
            "dm_support": True,
        }