"""
Sir Tim the Timely - Database Setup Script

This script initializes the SQLite database for Sir Tim the Timely Discord bot.
It creates all necessary tables and indices for storing deadline information,
user preferences, and reminder settings.
"""

import os
import sys
import logging
import asyncio
from pathlib import Path

from dotenv import load_dotenv
from src.database import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("database_setup")

async def setup_database():
    """Initialize the database with all required tables."""
    try:
        # Load environment variables
        load_dotenv()
        
        # Ensure data directory exists
        data_dir = Path("./data")
        data_dir.mkdir(exist_ok=True)
        
        # Get database path from environment or use default
        db_path = os.getenv("DATABASE_PATH", "./data/deadlines.db")
        
        # Initialize database manager
        db_manager = DatabaseManager(db_path)
        
        # Initialize database (creates tables)
        await db_manager.initialize()
        
        # Close database connection
        await db_manager.close()
        
        logger.info(f"Database successfully initialized at {db_path}")
        logger.info("You can now run the bot with: python main.py")
        
        return True
    
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False

def main():
    """Main entry point for database setup."""
    logger.info("Setting up Sir Tim the Timely database...")
    
    # Run the async setup function
    if os.name == 'nt':  # Windows
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    success = asyncio.run(setup_database())
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
