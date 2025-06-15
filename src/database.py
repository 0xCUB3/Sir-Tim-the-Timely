"""
Database Manager for Sir Tim the Timely

Handles all database operations for deadlines, user preferences, and reminders.
"""

import logging
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
# Register datetime adapter and converter to override deprecated defaults
sqlite3.register_adapter(datetime, lambda dt: dt.isoformat())
sqlite3.register_converter('DATETIME', lambda s: datetime.fromisoformat(s.decode()))
import aiosqlite


logger = logging.getLogger("sir_tim.database")

class DatabaseManager:
    """Manages the SQLite database for the bot."""
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: Optional[aiosqlite.Connection] = None
    
    async def initialize(self):
        """Initialize the database and create tables."""
        self._connection = await aiosqlite.connect(self.db_path)
        await self._create_tables()
        # Migrate legacy schema: add new columns if missing
        await self._migrate_schema()
        logger.info(f"Database initialized at {self.db_path}")
    
    async def close(self):
        """Close the database connection."""
        if self._connection:
            await self._connection.close()
            logger.info("Database connection closed")
    
    async def _create_tables(self):
        """Create all necessary database tables."""
        async with self._connection.cursor() as cursor:
            # Deadlines table
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS deadlines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    start_date DATETIME,
                    due_date DATETIME NOT NULL,
                    category TEXT,
                    url TEXT,
                    is_critical BOOLEAN DEFAULT FALSE,
                    is_event BOOLEAN DEFAULT FALSE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # User preferences table
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id INTEGER PRIMARY KEY,
                    timezone TEXT DEFAULT 'US/Eastern',
                    daily_reminder_time TEXT DEFAULT '09:00',
                    reminder_enabled BOOLEAN DEFAULT TRUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            
            # Server settings
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS server_settings (
                    guild_id INTEGER PRIMARY KEY,
                    reminder_channel_id INTEGER,
                    admin_role_id INTEGER,
                    announcement_enabled BOOLEAN DEFAULT TRUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await self._connection.commit()
        
        logger.info("Database tables created successfully")
    
    async def _migrate_schema(self):
        """Ensure new columns exist in deadlines table for migrations."""
        # Fetch existing columns
        async with self._connection.execute("PRAGMA table_info(deadlines)") as cursor:
            rows = await cursor.fetchall()
        existing = {row[1] for row in rows}
        # Add missing columns
        async with self._connection.cursor() as cursor:
            if 'start_date' not in existing:
                await cursor.execute("ALTER TABLE deadlines ADD COLUMN start_date DATETIME")
            if 'is_event' not in existing:
                await cursor.execute("ALTER TABLE deadlines ADD COLUMN is_event BOOLEAN DEFAULT 0")
            await self._connection.commit()
    
    async def add_deadline(self, title: str, description: str, due_date: datetime,
                          start_date: Optional[datetime] = None,
                          category: Optional[str] = None, url: Optional[str] = None,
                          is_critical: bool = False, is_event: bool = False) -> int:
        """Add a new deadline to the database, avoiding duplicates."""
        async with self._connection.cursor() as cursor:
            # Check for exact duplicates first
            await cursor.execute("""
                SELECT id FROM deadlines 
                WHERE title = ? AND due_date = ? AND category = ?
            """, (title, due_date, category))
            
            existing = await cursor.fetchone()
            if existing:
                logger.info(f"Duplicate deadline found: {title} - {due_date}")
                return existing[0]
            
            # Insert new deadline using INSERT OR IGNORE for extra safety
            await cursor.execute("""
                INSERT INTO deadlines (title, description, start_date, due_date, category, url, is_critical, is_event)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (title, description, start_date, due_date, category, url, is_critical, is_event))
            
            await self._connection.commit()
            return cursor.lastrowid or 0
    
    async def get_deadlines(self, category: Optional[str] = None, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get deadlines from the database."""
        query = "SELECT * FROM deadlines"
        params = []
        
        conditions = []
        if active_only:
            conditions.append("due_date > datetime('now')")
        if category:
            conditions.append("category = ?")
            params.append(category)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY due_date ASC"
        
        async with self._connection.cursor() as cursor:
            await cursor.execute(query, params)
            rows = await cursor.fetchall()
            
            # Convert to dictionaries
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    
    async def update_deadline(self, deadline_id: int, **kwargs) -> bool:
        """Update a deadline in the database."""
        if not kwargs:
            return False
        
        # Build update query
        set_clauses = []
        params = []
        
        for key, value in kwargs.items():
            if key in ['title', 'description', 'start_date', 'due_date', 'category', 'url', 'is_critical', 'is_event']:
                set_clauses.append(f"{key} = ?")
                params.append(value)
        
        if not set_clauses:
            return False
        
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        params.append(deadline_id)
        
        query = f"UPDATE deadlines SET {', '.join(set_clauses)} WHERE id = ?"
        
        async with self._connection.cursor() as cursor:
            await cursor.execute(query, params)
            await self._connection.commit()
            return cursor.rowcount > 0
    
    async def delete_deadline(self, deadline_id: int) -> bool:
        """Delete a deadline from the database."""
        async with self._connection.cursor() as cursor:
            await cursor.execute("DELETE FROM deadlines WHERE id = ?", (deadline_id,))
            await self._connection.commit()
            return cursor.rowcount > 0
    
    async def get_user_preferences(self, user_id: int) -> Dict[str, Any]:
        """Get user preferences."""
        async with self._connection.cursor() as cursor:
            await cursor.execute(
                "SELECT * FROM user_preferences WHERE user_id = ?", 
                (user_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            else:
                # Return default preferences
                return {
                    'user_id': user_id,
                    'timezone': 'US/Eastern',
                    'daily_reminder_time': '09:00',
                    'reminder_enabled': True
                }
    
    async def update_user_preferences(self, user_id: int, **kwargs) -> bool:
        """Update or insert user preferences."""
        # Check if user exists
        async with self._connection.cursor() as cursor:
            await cursor.execute(
                "SELECT user_id FROM user_preferences WHERE user_id = ?", 
                (user_id,)
            )
            exists = await cursor.fetchone()
            
            if exists:
                # Update existing preferences
                set_clauses = []
                params = []
                
                for key, value in kwargs.items():
                    if key in ['timezone', 'daily_reminder_time', 'reminder_enabled']:
                        set_clauses.append(f"{key} = ?")
                        params.append(value)
                
                if set_clauses:
                    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
                    params.append(user_id)
                    
                    query = f"UPDATE user_preferences SET {', '.join(set_clauses)} WHERE user_id = ?"
                    await cursor.execute(query, params)
            else:
                # Insert new preferences
                columns = ['user_id']
                values = [user_id]
                placeholders = ['?']
                
                for key, value in kwargs.items():
                    if key in ['timezone', 'daily_reminder_time', 'reminder_enabled']:
                        columns.append(key)
                        values.append(value)
                        placeholders.append('?')
                
                query = f"INSERT INTO user_preferences ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                await cursor.execute(query, values)
            
            await self._connection.commit()
            return True
    
    
    
    async def search_deadlines(self, query: str) -> List[Dict[str, Any]]:
        """Search deadlines by title or description."""
        search_query = f"%{query}%"
        
        async with self._connection.cursor() as cursor:
            await cursor.execute("""
                SELECT * FROM deadlines
                WHERE (title LIKE ? OR description LIKE ?)
                AND due_date > datetime('now')
                ORDER BY due_date ASC
            """, (search_query, search_query))
            
            rows = await cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    
    async def get_upcoming_deadlines(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get deadlines and events in the next N days."""
        async with self._connection.cursor() as cursor:
            query = f"""
                SELECT * FROM deadlines
                WHERE (
                    due_date BETWEEN datetime('now') AND datetime('now', '+{days} days')
                ) OR (
                    is_event = 1
                    AND start_date IS NOT NULL
                    AND start_date BETWEEN datetime('now') AND datetime('now', '+{days} days')
                )
                ORDER BY due_date ASC
            """
            await cursor.execute(query)
            rows = await cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    
    async def find_duplicate_deadlines(self) -> List[Dict[str, Any]]:
        """Find potential duplicate deadlines based on similar titles and categories."""
        async with self._connection.cursor() as cursor:
            # Find deadlines with similar titles (after basic normalization)
            await cursor.execute("""
                SELECT d1.id as id1, d1.title as title1, d1.due_date as due_date1, d1.category as category1,
                       d2.id as id2, d2.title as title2, d2.due_date as due_date2, d2.category as category2
                FROM deadlines d1
                JOIN deadlines d2 ON d1.id < d2.id
                WHERE d1.category = d2.category
                AND (
                    -- Exact title match
                    d1.title = d2.title
                    OR
                    -- Similar titles (basic check)
                    (LENGTH(d1.title) > 10 AND LENGTH(d2.title) > 10 AND
                     SUBSTR(d1.title, 1, LENGTH(d1.title)/2) = SUBSTR(d2.title, 1, LENGTH(d2.title)/2))
                )
                ORDER BY d1.category, d1.title
            """)
            
            rows = await cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    
    async def cleanup_old_deadlines(self, days_old: int = 30) -> int:
        """Remove deadlines that are older than the specified number of days."""
        async with self._connection.cursor() as cursor:
            await cursor.execute("""
                DELETE FROM deadlines 
                WHERE due_date < datetime('now', '-{} days')
            """.format(days_old))
            
            await self._connection.commit()
            return cursor.rowcount
    
    async def merge_deadlines(self, keep_id: int, remove_id: int) -> bool:
        """Merge two deadlines by keeping one and removing the other."""
        async with self._connection.cursor() as cursor:
            # Check that both deadlines exist
            await cursor.execute("SELECT id FROM deadlines WHERE id IN (?, ?)", (keep_id, remove_id))
            existing = await cursor.fetchall()
            
            if len(existing) != 2:
                return False
            
            # Remove the duplicate deadline
            await cursor.execute("DELETE FROM deadlines WHERE id = ?", (remove_id,))
            await self._connection.commit()
            
            return cursor.rowcount > 0
