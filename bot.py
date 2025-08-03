"""
Sir Tim the Timely - MIT Deadline Discord Bot

A sophisticated Discord bot built with Hikari and Hikari-Arc that helps MIT 
first-year students stay on top of critical summer deadlines and orientation tasks.
"""

import os
import logging
import asyncio
from pathlib import Path

import hikari
import arc
import miru
from dotenv import load_dotenv

from src.database import DatabaseManager
from src.scraper import MITDeadlineScraper
from src.ai_handler import AIHandler
from src.reminder_system import ReminderSystem
from src.gemini_chat_handler import GeminiChatHandler

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("sir_tim")

class SirTimBot:
    """Main bot class for Sir Tim the Timely."""
    
    def __init__(self):
        # Validate required environment variables
        self.token = os.getenv("TOKEN")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        
        if not self.token:
            raise ValueError("Discord TOKEN not found in environment variables")
        if not self.gemini_api_key:
            logger.warning("GEMINI_API_KEY not found - AI features will be disabled")
        
        # Initialize Hikari bot
        self.bot = hikari.GatewayBot(
            token=self.token,
            intents=(
                hikari.Intents.GUILDS
                | hikari.Intents.GUILD_MESSAGES
                | hikari.Intents.MESSAGE_CONTENT
                | hikari.Intents.DM_MESSAGES
            )
        )
        
        # Initialize Arc client
        self.client = arc.GatewayClient(self.bot)
        
        # Initialize Miru client for interactive components
        self.miru_client = miru.Client(self.bot, ignore_unknown_interactions=True)
        
        # Initialize components
        self.db_manager = None
        self.scraper = None
        self.ai_handler = None
        self.reminder_system = None
        self.gemini_chat_handler = None
        
    async def setup_components(self):
        """Initialize all bot components."""
        try:
            # Ensure data directory exists
            data_dir = Path("./data")
            data_dir.mkdir(exist_ok=True)
            
            # Initialize database
            self.db_manager = DatabaseManager(os.getenv("DATABASE_PATH", "./data/deadlines.db"))
            await self.db_manager.initialize()
            logger.info("Database initialized successfully")
            
            # Initialize AI handler first if API key available
            if self.gemini_api_key:
                self.ai_handler = AIHandler(self.gemini_api_key, self.db_manager)
                logger.info("AI handler initialized with Gemini API")
            else:
                self.ai_handler = None
                logger.warning("AI handler disabled - no API key provided")
            
            # Initialize scraper with AI handler
            mit_url = os.getenv("MIT_DEADLINES_URL", "https://firstyear.mit.edu/orientation/countdown-to-campus-before-you-arrive/critical-summer-actions-and-deadlines/")
            self.scraper = MITDeadlineScraper(mit_url, self.db_manager, self.ai_handler)
            logger.info("MIT deadline scraper initialized")
            
            # Initialize reminder system
            self.reminder_system = ReminderSystem(self.bot, self.db_manager, self.ai_handler)
            logger.info("Reminder system initialized")
            
            # Initialize the Gemini chat handler for contextual chat responses
            if self.gemini_api_key:
                self.gemini_chat_handler = GeminiChatHandler(api_key=self.gemini_api_key, db_manager=self.db_manager, bot=self.bot)
                logger.info("Gemini chat handler initialized for advanced contextual chat.")
            else:
                logger.warning("Gemini chat handler is disabled, no GEMINI_API_KEY provided.")

            # Set up dependency injection
            self.client.set_type_dependency(DatabaseManager, self.db_manager)
            self.client.set_type_dependency(MITDeadlineScraper, self.scraper)
            self.client.set_type_dependency(ReminderSystem, self.reminder_system)
            self.client.set_type_dependency(miru.Client, self.miru_client)
            if self.ai_handler:
                self.client.set_type_dependency(AIHandler, self.ai_handler)
            if self.gemini_chat_handler:
                self.client.set_type_dependency(GeminiChatHandler, self.gemini_chat_handler)
            
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            raise
    
    async def load_extensions(self):
        """Load all command extensions."""
        try:
            # Load all command modules - no need for interface switching
            extensions = [
                "src.commands.simplified_interface",  # /tim, /urgent, /setup
                "src.commands.deadlines",            # /deadlines list/next/search/etc
                "src.commands.admin",                # /admin commands
                "src.commands.utils",                # utility commands
                "src.commands.chat",                 # /setchat, /removechat, /chatstatus
            ]
            logger.info("Loading all command interfaces")
            
            for extension in extensions:
                try:
                    self.client.load_extension(extension)
                    logger.info(f"Loaded extension: {extension}")
                except Exception as e:
                    logger.error(f"Failed to load extension {extension}: {e}")
            
        except Exception as e:
            logger.error(f"Failed to load extensions: {e}")
            raise
    
    async def on_starting(self, event: hikari.StartingEvent) -> None:
        """Bot startup handler."""
        logger.info("Sir Tim the Timely is starting up...")
        await self.setup_components()
    
    async def on_started(self, event: hikari.StartedEvent) -> None:
        """Bot started handler."""
        logger.info("Sir Tim the Timely has started successfully!")
        # Set bot presence to show as online with an activity
        await self.bot.update_presence(
            status=hikari.Status.ONLINE,
            activity=hikari.Activity(
                name="deadlines approach",
                type=hikari.ActivityType.WATCHING
            )
        )
        # Scrape deadlines once at startup
        if self.scraper:
            await self.scraper.scrape_deadlines()
        # Start reminder system as a background task if needed
        if self.reminder_system:
            asyncio.create_task(self.reminder_system.start_reminder_loop())
        logger.info("Background tasks started - deadlines scraped and reminders scheduled")
    
    async def on_stopping(self, event: hikari.StoppingEvent) -> None:
        """Bot stopping handler."""
        logger.info("Sir Tim the Timely is shutting down...")
        if self.db_manager:
            await self.db_manager.close()
            
    async def on_message(self, event: hikari.MessageCreateEvent) -> None:
        """Handle incoming messages from both guilds and DMs."""
        # Main conversational AI uses Gemini if available
        if self.gemini_chat_handler:
            await self.gemini_chat_handler.handle_message(event)
    
    # Note: This method is no longer used; the setup is done directly in main()
    async def load_and_start(self):
        """Load extensions and start the bot (async method)."""
        try:
            # Load extensions
            await self.load_extensions()
            
            # Start the bot asynchronously
            await self.bot.start()
            
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            raise

def main():
    """Main entry point."""
    try:
        # Create the bot instance
        sir_tim = SirTimBot()
        
        # Configure event loop policy if on Windows
        if os.name == 'nt':  # Windows
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        # Setup event listeners
        sir_tim.bot.event_manager.subscribe(hikari.StartingEvent, sir_tim.on_starting)
        sir_tim.bot.event_manager.subscribe(hikari.StartedEvent, sir_tim.on_started)
        sir_tim.bot.event_manager.subscribe(hikari.StoppingEvent, sir_tim.on_stopping)
        sir_tim.bot.event_manager.subscribe(hikari.MessageCreateEvent, sir_tim.on_message)
        
        # Load extensions before running (need to use asyncio.run for this async operation)
        asyncio.run(sir_tim.load_extensions())
        
        # Run the bot with activity status - this is a blocking call
        sir_tim.bot.run(
            activity=hikari.Activity(
                name="deadlines approach", 
                type=hikari.ActivityType.WATCHING
            )
        )
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Critical error: {e}")
        raise

if __name__ == "__main__":
    main()