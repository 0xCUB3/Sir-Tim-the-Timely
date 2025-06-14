# Sir Tim the Timely - Source Code Documentation

This directory contains the core Python modules that power the Sir Tim the Timely Discord bot. Here's a guide to the codebase structure.

## Core Components

### `database.py`
- **Class:** `DatabaseManager`
- **Purpose:** Handles all database operations using SQLite with async support
- **Key Features:**
  - Table creation and schema management
  - CRUD operations for deadlines, user preferences, and reminders
  - Query support for deadline filtering and search

### `scraper.py`
- **Class:** `MITDeadlineScraper`
- **Purpose:** Extracts deadline information from the MIT First Year website
- **Key Features:**
  - Asynchronous web scraping using aiohttp and BeautifulSoup4
  - Deadline parsing and categorization
  - Automatic periodic scraping with configurable intervals

### `ai_handler.py`
- **Class:** `AIHandler`
- **Purpose:** Handles natural language queries using Google's Gemini API
- **Key Features:**
  - Query understanding and intent detection
  - Deadline search by natural language
  - Context-aware responses with MIT-specific knowledge

### `reminder_system.py`
- **Class:** `ReminderSystem`
- **Purpose:** Manages all scheduled reminders and notifications
- **Key Features:**
  - Time-based reminder scheduling
  - Personalized notifications based on user preferences
  - Support for different reminder frequencies based on deadline proximity

## Command Structure

The `commands/` directory contains all slash command implementations organized into logical groups:

### `deadlines.py`
- Commands for listing, searching, and managing deadlines
- Support for deadline filtering by category, date range, etc.
- Commands for setting personal reminders

### `admin.py`
- Admin-only commands for managing the bot
- Deadline override and manual additions
- Server configuration settings

### `utils.py`
- Utility commands for users
- Timezone preferences and notification settings
- Bot status and information

## Adding New Commands

To add a new command:

1. Identify the appropriate file in the `commands/` directory
2. Use the Hikari-Arc plugin structure with `@plugin.include` decorator
3. Add your command using the `@arc.slash` decorator
4. Register any options with proper type hints
5. Implement your command logic

Example:
```python
@plugin.include
@arc.slash("deadlines", "Commands for managing deadlines")
class DeadlinesGroup:
    
    @arc.slash.subcommand("list", "List all deadlines")
    async def list_deadlines(self, ctx: arc.GatewayContext) -> None:
        # Command implementation
        await ctx.respond("Listing all deadlines...")
```

## Development Workflow

1. Make your changes to the relevant files
2. Test locally by running `python main.py`
3. Use the built-in error handling to catch and fix any issues
4. Submit pull requests with clear descriptions of changes
