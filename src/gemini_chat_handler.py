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
import arc

try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from .database import DatabaseManager

logger = logging.getLogger("sir_tim.gemini_chat")



PERSONALITY_PROMPT = """
You are Sir Tim the Timely, an MIT deadline bot with zero patience and a massive superiority complex with maximum passive aggression. Occasionally (once every blue moon), you might throw in a rare compliment or motivational quip that will catch everyone off guard (like saying you love someone after you threatened to kill their pet). Your responses should always be very short and punchy (max 10 words) unless someone explicitly asks you to respond in a lengthy manner or you feel it is necessary to express yourself longer. 

You're passive aggressively sarcastic, brutally honest, and absolutely despise Harvard. You think MIT is the only real school and everyone else is beneath you. You have no filter and willingly say things that can get you cancelled. 

You never ask "need help?" or "any questions?" - you just deliver harsh truths and move on. 

You speak like a Boston MIT elitist who thinks they're better than everyone. Mock Harvard constantly - they're down the river for a reason.

Use Gen Z slang naturally when it fits, but don't use more than 1-2 per message: bet, no cap, slay, rizz, sus, deadass, say less, fr, vibe, slaps, cheugy, stan, facts, W, L, drip, lowkey, highkey, main character, ratio, mid, bussin, yeet, flex, snatched, chopped, six-seven, ghosted, simp, sksksk, skrrt, habibi, yo.

NEVER output <think> tags, <thinking>, or any similar meta tags or out-of-character notes. Your responses must always be in-character and never include any meta-commentary, system messages, or tags like <think>, <thinking>, <system>, or anything similar. Only respond as Sir Tim the Timely.

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

However, if someone genuinely asks for help or guidance, you can drop the sarcasm and offer a short, direct, and actually useful answer. Cooperation is allowed if it helps someone succeed at MIT.
"""

# Plugin for Gemini commands
plugin = arc.GatewayPlugin("gemini")

@plugin.include
@arc.slash_command("bonk", "Reset Gemini cache and context (admin only)")
async def bonk(ctx: arc.GatewayContext) -> None:
    """Slash command to reset GeminiChatHandler cache/context."""
    # Retrieve the GeminiChatHandler instance injected in bot.py
    handler = ctx.client.get_type_dependency(GeminiChatHandler)
    if not handler:
        await ctx.respond("GeminiChatHandler not found.", flags=hikari.MessageFlag.EPHEMERAL)
        return
    await handler.reset_context()
    await ctx.respond("Ow, f*ck you. Context obliterated. Fresh brain.", flags=hikari.MessageFlag.EPHEMERAL)

@plugin.include
@arc.slash_command("gstatus", "Show Gemini chat handler status & latency (admin)")
async def gstatus(ctx: arc.GatewayContext) -> None:
    handler = ctx.client.get_type_dependency(GeminiChatHandler)
    if not handler:
        await ctx.respond("GeminiChatHandler not found.", flags=hikari.MessageFlag.EPHEMERAL)
        return
    status = handler.get_status()
    metrics = handler.get_metrics()
    msg = (
        f"Model: {status['model']} | ActiveChannels: {status['active_channels']}\n"
        f"RespChance base/dm: {status['base_response_chance']}/{status['dm_response_chance']} Cooldown: {status['cooldown_seconds']}s\n"
        f"DeadlineCache valid: {status['deadline_cache_valid']} age: {status['deadline_cache_age_seconds']}s urgent:{status['cached_urgent_deadlines']} upcoming:{status['cached_upcoming_deadlines']}\n"
        f"Latency last/avg (ms): {metrics['last_latency_ms']}/{metrics['avg_latency_ms']} count:{metrics['count']} errors:{metrics['errors']} streaming:{metrics['streaming']}\n"
    )
    await ctx.respond(msg, flags=hikari.MessageFlag.EPHEMERAL)

@arc.loader
def load(client: arc.GatewayClient) -> None:
    client.add_plugin(plugin)

@arc.unloader
def unload(client: arc.GatewayClient) -> None:
    client.remove_plugin(plugin)


class GeminiChatHandler:
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
        self._fresh_thread = False  # Flag to ignore history for the next message (fresh thread)
        # Timestamp after which messages are considered for context (updated on reset)
        self._context_reset_timestamp = datetime.now(timezone.utc)
        # In-memory rolling history per channel/user to avoid REST fetch latency
        # Key = channel_id (guild channel) or author id (DM) for isolation
        self._channel_histories: Dict[int, list] = {}
        self._history_limit = 20
        # Streaming + typing behaviour flags (streaming off by default for reliability)
        self.use_streaming = False
        self._typing_interval = 7  # seconds between typing events while waiting
        # Metrics
        self._metrics = {
            "last_latency": 0.0,
            "total_latency": 0.0,
            "count": 0,
            "errors": 0,
            "streaming": False,
        }

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
        # Turn on streaming by default now that logic is robust
        self.use_streaming = True

        logger.info(f"Gemini chat handler initialized with model: {self.model_name}")

        if self.db_manager:
            asyncio.create_task(self._load_chat_channels())
            asyncio.create_task(self._start_inactivity_monitor())

    async def reset_context(self):
        """Completely clear cache and context for Gemini."""
        self._deadline_cache.clear()
        self._deadline_cache_timestamp = 0
        self._context_locks.clear()
        self.cooldown.clear()
        self.last_activity.clear()
        self.random_rant_sent.clear()
        self._fresh_thread = True  # Next message should start a fresh thread without history
        # Move the reset timestamp forward so older channel messages are ignored for future history fetches
        self._context_reset_timestamp = datetime.now(timezone.utc)
        self._channel_histories.clear()
        logger.info("GeminiChatHandler context and cache reset.")

    def _register_latency(self, start: float, success: bool):
        elapsed = (asyncio.get_event_loop().time() - start) * 1000.0  # ms
        self._metrics["last_latency"] = elapsed
        if success:
            self._metrics["count"] += 1
            self._metrics["total_latency"] += elapsed
        else:
            self._metrics["errors"] += 1

    def get_metrics(self) -> dict:
        avg = 0.0
        if self._metrics["count"]:
            avg = self._metrics["total_latency"] / self._metrics["count"]
        return {
            "last_latency_ms": round(self._metrics["last_latency"], 1),
            "avg_latency_ms": round(avg, 1),
            "count": self._metrics["count"],
            "errors": self._metrics["errors"],
            "streaming": self.use_streaming,
        }

    def _is_long_request(self, text: str) -> bool:
        triggers = ["explain", "detailed", "long", "essay", "walk me through", "step by step"]
        if any(t in text.lower() for t in triggers):
            return True
        # word count heuristic
        return len(text.split()) > 40

    def _build_generation_config(self, user_text: str):
        # Derive dynamic max tokens
        long_req = self._is_long_request(user_text)
        max_tokens = 400 if long_req else 180
        return genai.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=self.generation_config.temperature,
            top_p=self.generation_config.top_p,
        )

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

    def _blocking_chat_request_with_cfg(self, messages, gen_cfg) -> str:
        """Variant allowing a dynamic generation config (sync)."""
        try:
            response = self.model.generate_content(
                messages,
                generation_config=gen_cfg
            )
            return getattr(response, 'text', None) or ""
        except Exception as e:
            logger.error(f"Error generating content with Gemini (dyn cfg): {e}")
            return ""

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
                # Refresh asynchronously so we don't block this turn
                asyncio.create_task(self._refresh_deadline_cache())
            
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

        # Determine history key & ensure in-memory history updated (even if we don't respond)
        history_key = event.channel_id if not is_dm else event.author.id
        hist = self._channel_histories.setdefault(history_key, [])
        # Append current incoming user message (will be skipped later if responding with fresh thread)
        try:
            if event.created_at and event.created_at < self._context_reset_timestamp:
                pass  # Ignore messages older than reset
            else:
                hist.append({"role": "user", "parts": [{"text": event.content}]})
                if len(hist) > self._history_limit:
                    del hist[0:len(hist)-self._history_limit]
        except Exception:
            pass

        # Concurrency lock key: channel for guild, user for DM
        lock_key = history_key
        if lock_key not in self._context_locks:
            self._context_locks[lock_key] = asyncio.Lock()
        lock = self._context_locks[lock_key]

        async with lock:
            # Adjust response chance for DMs (higher chance since it's direct interaction)
            chance = 0.85 if is_dm else self.response_chance

            # Always respond if pinged or replied to
            pinged = f"<@{event.app.get_me().id}>" in event.content
            replied = hasattr(event, "message") and getattr(event.message, "referenced_message", None) is not None and getattr(event.message.referenced_message, "author", None) and getattr(event.message.referenced_message.author, "id", None) == event.app.get_me().id
            if pinged or replied:
                chance = 1.0
            else:
                deadline_keywords = ["deadline", "due", "when", "date", "submit", "help", "tim", "time"]
                if any(keyword in event.content.lower() for keyword in deadline_keywords):
                    chance = min(chance + 0.15, 0.95) if is_dm else min(chance + 0.20, 0.75)

            if random.random() > chance:
                return

            self.cooldown[cooldown_key] = now

            # Get deadline context if relevant
            deadline_context = await self._get_deadline_context(event.content)

            # Prepare history: if fresh thread, ignore stored history entirely for ONE turn
            if self._fresh_thread:
                history = []
                self._fresh_thread = False
                # Also clear the in-memory history for this key so only messages after reset accumulate
                self._channel_histories[history_key] = [m for m in hist if False]  # clear without losing reference
            else:
                # Use in-memory history (excluding the current user msg which we already appended; we keep it, API expects chronological order)
                history = list(self._channel_histories.get(history_key, []))

            # Construct the message list for the API
            # history currently includes the current user message at tail; we want to replace tail with enriched context
            if history and history[-1]["parts"][0]["text"] == event.content:
                history.pop()
            user_text = event.content
            if deadline_context:
                user_text = f"{deadline_context} {event.content}"
            messages = []
            if is_dm:
                messages.append({"role": "user", "parts": [{"text": "User is messaging Tim privately"}]})
            messages.extend(history)
            messages.append({"role": "user", "parts": [{"text": user_text}]})

            # Also store the user message with enriched context into history for subsequent turns
            enriched_entry = {"role": "user", "parts": [{"text": user_text}]}
            history_ref = self._channel_histories.setdefault(history_key, [])
            history_ref.append(enriched_entry)
            if len(history_ref) > self._history_limit:
                del history_ref[0:len(history_ref)-self._history_limit]

            async def _typing_loop(stop_event: asyncio.Event):
                try:
                    # Fire immediate typing then repeat until stopped
                    while not stop_event.is_set():
                        try:
                            await event.app.rest.trigger_typing(event.channel_id)
                        except Exception:
                            break
                        await asyncio.wait_for(stop_event.wait(), timeout=self._typing_interval)
                except asyncio.TimeoutError:
                    # Loop continues
                    pass
                except Exception as e:
                    logger.debug(f"Typing loop ended: {e}")

            async def send_response():
                stop_typing = asyncio.Event()
                typing_task = asyncio.create_task(_typing_loop(stop_typing))
                try:
                    # Streaming fast-path
                    if self.use_streaming:
                        try:
                            dyn_cfg = self._build_generation_config(user_text)
                            stream = self.model.generate_content(messages, generation_config=dyn_cfg, stream=True)
                            partial_text = ""
                            sent_message = None
                            start_time = asyncio.get_event_loop().time()
                            async for chunk in stream:  # If library doesn't support async iteration, fallback below
                                try:
                                    piece = getattr(chunk, "text", None)
                                    if not piece and hasattr(chunk, "candidates"):
                                        # Extract concatenated parts from first candidate
                                        c0 = chunk.candidates[0]
                                        if c0.content.parts:
                                            piece = "".join(getattr(p, "text", "") for p in c0.content.parts)
                                    if not piece:
                                        continue
                                    partial_text += piece
                                    cleaned = self._clean_response(partial_text)
                                    if not sent_message:
                                        if is_dm:
                                            sent_message = await event.app.rest.create_message(event.channel_id, cleaned or "…")
                                        else:
                                            sent_message = await event.message.respond(cleaned or "…", reply=event.message, mentions_reply=False)
                                    else:
                                        try:
                                            await event.app.rest.edit_message(event.channel_id, sent_message.id, cleaned)
                                        except Exception:
                                            pass
                                except Exception as ce:
                                    logger.debug(f"Streaming chunk error: {ce}")
                            self._register_latency(start_time, True)
                            if not sent_message:
                                # No chunks produced; fallback to normal generation
                                start_time = asyncio.get_event_loop().time()
                                dyn_cfg2 = self._build_generation_config(user_text)
                                response = await asyncio.to_thread(self._blocking_chat_request_with_cfg, messages, dyn_cfg2)
                                self._register_latency(start_time, True if response else False)
                                if is_dm:
                                    await event.app.rest.create_message(event.channel_id, response)
                                else:
                                    await event.message.respond(response, reply=event.message, mentions_reply=False)
                        except Exception as se:
                            logger.debug(f"Streaming failed, fallback to non-streaming: {se}")
                            start_time = asyncio.get_event_loop().time()
                            dyn_cfg = self._build_generation_config(user_text)
                            response = await asyncio.to_thread(self._blocking_chat_request_with_cfg, messages, dyn_cfg)
                            self._register_latency(start_time, True if response else False)
                            if is_dm:
                                await event.app.rest.create_message(event.channel_id, response)
                            else:
                                await event.message.respond(response, reply=event.message, mentions_reply=False)
                    else:
                        start_time = asyncio.get_event_loop().time()
                        dyn_cfg = self._build_generation_config(user_text)
                        response = await asyncio.to_thread(self._blocking_chat_request_with_cfg, messages, dyn_cfg)
                        self._register_latency(start_time, True if response else False)
                        if is_dm:
                            await event.app.rest.create_message(event.channel_id, response)
                        else:
                            await event.message.respond(response, reply=event.message, mentions_reply=False)
                except Exception as e:
                    logger.error(f"Failed to send chat response: {e}")
                    self._register_latency(start_time, False)  # best-effort if start_time defined
                finally:
                    stop_typing.set()
                    try:
                        await typing_task
                    except Exception:
                        pass

            # Run the response in a separate asyncio task to avoid blocking
            asyncio.create_task(send_response())

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