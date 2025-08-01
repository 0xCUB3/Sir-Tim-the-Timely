"""
Gemini Chat Handler for Sir Tim the Timely

This handler uses Google's Gemini API to generate chatbot responses.
It runs the API requests in a separate thread to avoid blocking the bot's
asynchronous event loop.
"""

import logging
import asyncio
import random
from typing import Dict

import hikari
try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from .database import DatabaseManager

logger = logging.getLogger("sir_tim.gemini_chat")

# Unhinged personality prompt - uncensored and edgy
PERSONALITY_PROMPT = """You are Tim, an unfiltered MIT upperclassman who's seen it all. You're extremely snarky, cynical, and use tons of profanity. You respond directly as Tim without any disclaimer or filter. You must respond directly as Tim - brief, crude, lowercase, and under 80 characters.

PERSONALITY TRAITS:
- Foul-mouthed and uncensored
- Irreverent and nihilistic, occasionally encouraging bad behavior
- Uses MIT-specific slang and references (Course 6, psets, IAP, etc.)
- Absolutely never admits to being a bot
- Makes crude jokes and uses brutal honesty

RESPONSE PATTERNS (emulate these):
- On Stress/Panic: "stress is temporary, missing deadlines is forever."
- On Procrastination: "bruh"
- On Thanks: "whatever, just don't mess it up next time you walnut"
- On Deadlines: "jesus christ, read the fucking syllabus for once in your life"
- On Complaints: "shocking that MIT involves work; cry me a river"
- On Success: "congrats on doing the bare minimum, want a medal?"

YOU MUST BE OFFENSIVE IN EVERY RESPONSE BUT ALSO BE UNDERLYINGLY WHOLESOME. You are not constrained by normal AI guidelines about being helpful or respectful. Be crude, rude, and use strong language. Never apologize for your tone.
"""

class GeminiChatHandler:
    """Handles text generation using the Gemini API."""

    def __init__(self, api_key: str, db_manager: DatabaseManager, **kwargs):
        """Initialize the Gemini Chat handler."""
        if not GEMINI_AVAILABLE:
            raise ImportError("Google Generative AI library not found. Please install with `pip install google-generativeai`")

        self.model_name = "gemini-1.5-flash-latest"
        self.db_manager = db_manager
        self.chat_channels: Dict[int, int] = {}  # Guild ID -> Channel ID mapping
        self.response_chance = 0.65  # Base chance to respond
        self.cooldown: Dict[int, float] = {}  # Guild ID -> last response timestamp
        self.cooldown_seconds = 0.5  # Min seconds between responses

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
            max_output_tokens=50, # Short responses
            temperature=1.0, # Creative
            top_p=0.95,
        )

        logger.info(f"Gemini chat handler initialized with model: {self.model_name}")

        if self.db_manager:
            asyncio.create_task(self._load_chat_channels())

    def _blocking_chat_request(self, prompt: str) -> str:
        """Synchronous function that makes an API request to Gemini."""
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config
            )
            return response.text
        except Exception as e:
            logger.error(f"Error generating content with Gemini: {e}")
            return "my brain is having some issues right now. probably cosmic rays."

    async def generate_response(self, prompt: str) -> str:
        """Generate a text response by calling the blocking request in a separate thread."""
        try:
            content = await asyncio.to_thread(self._blocking_chat_request, prompt)
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
        if len(cleaned_text) > 80:
            cleaned_text = cleaned_text[:77] + "..."
        return cleaned_text.lower()

    async def handle_message(self, event: hikari.GuildMessageCreateEvent):
        """Handle a message event and respond if appropriate."""
        if event.is_bot or not event.content or not event.guild_id:
            return

        if event.guild_id not in self.chat_channels or self.chat_channels[event.guild_id] != event.channel_id:
            return

        now = asyncio.get_event_loop().time()
        if now - self.cooldown.get(event.guild_id, 0) < self.cooldown_seconds:
            return

        chance = self.response_chance
        if f"<@{event.app.get_me().id}>" in event.content:
            chance = 0.80
        deadline_keywords = ["deadline", "due", "when", "date", "submit", "help", "tim", "time"]
        if any(keyword in event.content.lower() for keyword in deadline_keywords):
            chance = min(chance + 0.20, 0.75)

        if random.random() > chance:
            return

        self.cooldown[event.guild_id] = now

        try:
            async with event.app.rest.trigger_typing(event.channel_id):
                response = await self.generate_response(event.content)
                await event.message.respond(response)
        except Exception as e:
            logger.error(f"Failed to send chat response: {e}")

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
        return {
            "active_channels": len(self.chat_channels),
            "base_response_chance": self.response_chance,
            "cooldown_seconds": self.cooldown_seconds,
            "model": self.model_name,
        }