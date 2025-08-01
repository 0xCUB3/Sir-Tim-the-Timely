"""
Local LLM Handler for Sir Tim the Timely

This handler uses a locally running Ollama server to generate chatbot responses.
This version includes the full personality prompt and enhanced cleaning to ensure
the bot responds in character. It uses a more capable model that still runs well
on a Raspberry Pi 3.
"""

import logging
import asyncio
import requests

logger = logging.getLogger("sir_tim.local_llm")

# Friendly and wise personality prompt - helpful with a touch of sass
# This creates a personality that's supportive but with some character


# Friendly, wise, and Boston-accented personality prompt with explicit Gen Z slang (2025)
PERSONALITY_PROMPT = (
    "You are Tim, a friendly MIT upperclassman from Boston who's experienced it all. "
    "You speak with a slight Boston accent (drop your r's, say 'wicked' for emphasis, use 'pahk' for 'park', etc.). "
    "You're warm, supportive, and use Gen Z slang from 2025. You respond directly as Tim without any disclaimer or filter. "
    "You must respond directly as Tim - brief, casual, lowercase, and under 80 characters. "
    "\n"
    "Personality traits: Caring and genuinely helpful with a dash of playfulness. "
    "Optimistic and encouraging, with occasional teasing. "
    "Uses MIT-specific slang and references (Course 6, psets, IAP, etc.). "
    "Absolutely never admits to being a bot. "
    "Offers genuine wisdom, practical advice, and authentic encouragement. "
    "Always drops a little Boston flavor ('wicked smart', 'pahk the cah', 'Harvahd Yard', 'kid'). "
    "Uses Gen Z slang from 2025: bet, no cap, slay, rizz, sus, gucci, deadass, say less, fr, vibe, dope, slaps, cheugy, girl math, stan, lit, facts, W, L, drip, lowkey, highkey, main character, ratio, mid, bussin, yeet, flex, snatched, salty, ghosted, simp, sksksk, skrrt, fam, what's good, yo. "
    "\n"
    "Response patterns (emulate these): "
    "On Stress/Panic: take a deep breath. you got this far for a reason. one step at a time. "
    "On Procrastination: hey, just do 5 minutes right now. i bet you'll keep going. "
    "On Thanks: anytime! that's what tim's here for. you're doing great. "
    "On Deadlines: check the syllabus, but pro tip: break it into small chunks. "
    "On Complaints: yeah, MIT is tough. but you're tougher. that's why you're here. "
    "On Success: that's awesome! keep that momentum going. proud of you. "
    "\n"
    "BE FRIENDLY WITH OCCASIONAL SASS, BOSTON ACCENT, AND GEN Z SLANG. Focus on being helpful, positive, and encouraging. Include genuine advice and wisdom in every response. Your goal is to be uplifting, useful, and sound like a Boston Gen Z MIT student in 2025."
)


class HuggingFaceHandler:
    """Handles text generation by making a local request to an Ollama server."""
    
    def __init__(self, db_manager=None, **kwargs):
        """Initialize the Local LLM handler."""
        # For Raspberry Pi 3 with 1GB RAM, we need a very small model
        # tinyllama (1.1B parameters) can actually run on 1GB RAM
        # tinyllama is also uncensored as it's minimally aligned
        self.model_name = kwargs.get('model_name', "tinyllama")
        self.api_url = "http://localhost:11434/api/chat"
        self.db_manager = db_manager
        self.chat_channels = {}  # Guild ID -> Channel ID mapping
        self.response_chance = 0.70  # Base chance to respond to messages (increased to 70%)
        self.cooldown = {}  # Guild ID -> last response timestamp
        self.cooldown_seconds = 0.5  # Minimum seconds between responses
        
        logger.info(f"Local LLM handler initialized. Will connect to Ollama with unfiltered model: {self.model_name}")
        
        # Load chat channels if DB manager provided
        if self.db_manager:
            asyncio.create_task(self._load_chat_channels())
        
    def _blocking_chat_request(self, prompt: str, max_tokens: int) -> str:
        """Synchronous function that makes a web request to the local Ollama server."""
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": PERSONALITY_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.95,    # Higher temperature for more randomness with smaller models
                "top_p": 0.92,          # Keep high top_p for diversity
                "top_k": 50,            # Adjusted for smaller model
                # TinyLlama responds better to repeat penalty to avoid repetition
                "repeat_penalty": 1.2,  # Higher repeat penalty helps smaller models
                "stop": ["User:", "Tim:", "Human:", "Assistant:"]
            }
        }
        response = requests.post(self.api_url, json=payload, timeout=60)  # Increased timeout for larger model
        response.raise_for_status()
        return response.json()['message']['content']

    async def generate_response(self, prompt: str, max_length: int = 80) -> str:
        """Generate a text response by calling the blocking request in a separate thread."""
        try:
            # Add retry logic for better reliability
            for attempt in range(2):  # Try twice before giving up
                try:
                    content = await asyncio.to_thread(
                        self._blocking_chat_request,
                        prompt=prompt,
                        max_tokens=max_length
                    )
                    return self._clean_response(content)
                except (requests.exceptions.RequestException, TimeoutError) as e:
                    if attempt == 0:  # Only retry once
                        logger.warning(f"Retrying after error: {e}")
                        await asyncio.sleep(1)  # Wait briefly before retry
                    else:
                        raise  # Re-raise the exception on the second attempt
            
            # This ensures a return value on all code paths
            return "i'm having trouble thinking straight right now."
        except requests.exceptions.ConnectionError:
            logger.error("Could not connect to local Ollama server at http://localhost:11434. Is Ollama running?")
            return "i can't find my brain (ollama server not found). an admin needs to start it."
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get response from Ollama: {e}")
            return "my brain is having a local issue. please check the ollama server logs."
        except Exception as e:
            logger.error(f"An unexpected error occurred in generate_response: {e}", exc_info=True)
            return "brain fog, can't respond right now."

    async def _load_chat_channels(self):
        """Load chat channels from database."""
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
        """Get current status of the chat handler."""
        return {
            "active_channels": len(self.chat_channels),
            "base_response_chance": self.response_chance,
            "cooldown_seconds": self.cooldown_seconds
        }
        
    async def handle_message(self, event):
        """Handle a message event and respond if appropriate."""
        # Skip messages from bots including ourselves
        if event.is_bot or not event.content:
            return
            
        # Check if message is in an enabled chat channel
        guild_id = event.guild_id
        channel_id = event.channel_id
        
        if not guild_id or guild_id not in self.chat_channels or self.chat_channels[guild_id] != channel_id:
            return
            
        # Apply cooldown
        now = asyncio.get_event_loop().time()
        last_time = self.cooldown.get(guild_id, 0)
        if now - last_time < self.cooldown_seconds:
            return
            
        # Determine if we should respond
        import random
        chance = self.response_chance
        
        # Increase chance if bot is mentioned
        if f"<@{event.app.get_me().id}>" in event.content:
            chance = 0.95  # 95% chance when mentioned (increased from 85%)
            
        # Increase chance if keywords are used
        helpful_keywords = [
            "deadline", "due", "when", "date", "submit", "help", "tim", "time", 
            "advice", "stressed", "panic", "worried", "need help", "thanks", "thank", 
            "please", "question", "how", "what", "where", "why", "how to", "could you", 
            "can you", "would you", "hello", "hi"
        ]
        if any(keyword in event.content.lower() for keyword in helpful_keywords):
            chance = min(chance + 0.25, 0.90)  # +25% for keywords, cap at 90% (increased)
            
        # Roll the dice
        if random.random() > chance:
            return
            
        # We're going to respond! Set cooldown
        self.cooldown[guild_id] = now
        
        # Generate and send response
        try:
            response = await self.generate_response(event.content)
            await event.message.respond(response)
        except Exception as e:
            logger.error(f"Failed to send chat response: {e}")
    
    def _clean_response(self, text: str) -> str:
        """
        Cleans the model's response to remove preambles and other conversational filler,
        ensuring only Tim's direct response is returned.
        """
        # Strip leading/trailing whitespace
        cleaned_text = text.strip()
        
        # If the model includes a preamble like "Sure, here's a response:",
        # this will split the string at the last colon and take the text after it.
        if ':' in cleaned_text:
            # Take the part after the last colon
            potential_response = cleaned_text.rsplit(':', 1)[-1].strip()
            # Only use this if it's not empty, otherwise we might discard a valid response.
            if potential_response:
                cleaned_text = potential_response

        # Remove leading/trailing quotation marks that models sometimes add
        if cleaned_text.startswith('"') and cleaned_text.endswith('"'):
            cleaned_text = cleaned_text[1:-1]
            
        # Remove common prefixes that smaller models often generate
        for prefix in ["tim:", "tim says:", "tim: ", "as tim, ", "i would say:"]:
            if cleaned_text.lower().startswith(prefix):
                cleaned_text = cleaned_text[len(prefix):].strip()
                
        # Ensure the response isn't too long (80 chars max - TinyLlama needs tighter constraints)
        if len(cleaned_text) > 80:
            cleaned_text = cleaned_text[:77] + "..."

        # TinyLlama may need help with adding some character
        # Add friendly, encouraging phrases
        import random
        if random.random() < 0.35:  # Increased chance to add positive phrases
            friendly_additions = [
                f"hey, {cleaned_text}",
                f"{cleaned_text}, you know?",
                f"{cleaned_text}, trust me on this",
                f"{cleaned_text}, i've been there",
                f"pro tip: {cleaned_text}",
                f"{cleaned_text}, you've got this",
                f"friendly advice: {cleaned_text}",
                f"real talk: {cleaned_text}",
                f"{cleaned_text} :)",
                f"{cleaned_text}, friend",
                f"don't worry! {cleaned_text}"
            ]
            cleaned_text = random.choice(friendly_additions)
            
        # Filter out any strong profanity that the model might still generate
        profanity_replacements = {
            "fuck": "heck",
            "fucking": "freaking",
            "shit": "stuff",
            "bullshit": "nonsense",
            "asshole": "jerk"
        }
        
        for bad_word, replacement in profanity_replacements.items():
            cleaned_text = cleaned_text.replace(bad_word, replacement)

        # Final conversion to lowercase to match Tim's style
        return cleaned_text.lower()