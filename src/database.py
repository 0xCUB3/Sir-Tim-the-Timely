"""
Database Manager for Sir Tim the Timely

Handles all database operations for deadlines, user preferences, and reminders.
"""

import logging
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Any, Union
from datetime import datetime, timezone
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
                    due_date DATETIME NOT NULL,
                    category TEXT,
                    url TEXT,
                    is_critical BOOLEAN DEFAULT FALSE,
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
            
            # User deadline tracking
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_deadlines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    deadline_id INTEGER NOT NULL,
                    completed BOOLEAN DEFAULT FALSE,
                    reminder_time DATETIME,
                    notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (deadline_id) REFERENCES deadlines (id)
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
    
    async def add_deadline(self, title: str, description: str, due_date: datetime, 
                          category: Optional[str] = None, url: Optional[str] = None, is_critical: bool = False) -> int:
        """Add a new deadline to the database."""
        async with self._connection.cursor() as cursor:
            await cursor.execute("""
                INSERT INTO deadlines (title, description, due_date, category, url, is_critical)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (title, description, due_date, category, url, is_critical))
            
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
            if key in ['title', 'description', 'due_date', 'category', 'url', 'is_critical']:
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
    
    async def mark_deadline_completed(self, user_id: int, deadline_id: int, completed: bool = True) -> bool:
        """Mark a deadline as completed for a user."""
        async with self._connection.cursor() as cursor:
            # Check if record exists
            await cursor.execute("""
                SELECT id FROM user_deadlines 
                WHERE user_id = ? AND deadline_id = ?
            """, (user_id, deadline_id))
            
            exists = await cursor.fetchone()
            
            if exists:
                # Update existing record
                await cursor.execute("""
                    UPDATE user_deadlines 
                    SET completed = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND deadline_id = ?
                """, (completed, user_id, deadline_id))
            else:
                # Insert new record
                await cursor.execute("""
                    INSERT INTO user_deadlines (user_id, deadline_id, completed)
                    VALUES (?, ?, ?)
                """, (user_id, deadline_id, completed))
            
            await self._connection.commit()
            return True
    
    async def get_user_deadline_status(self, user_id: int, deadline_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get deadline completion status for a user."""
        query = """
            SELECT ud.*, d.title, d.due_date, d.category
            FROM user_deadlines ud
            JOIN deadlines d ON ud.deadline_id = d.id
            WHERE ud.user_id = ?
        """
        params = [user_id]
        
        if deadline_id:
            query += " AND ud.deadline_id = ?"
            params.append(deadline_id)
        
        query += " ORDER BY d.due_date ASC"
        
        async with self._connection.cursor() as cursor:
            await cursor.execute(query, params)
            rows = await cursor.fetchall()
            
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    
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
        """Get deadlines in the next N days."""
        async with self._connection.cursor() as cursor:
            await cursor.execute("""
                SELECT * FROM deadlines
                WHERE due_date BETWEEN datetime('now') AND datetime('now', '+{} days')
                ORDER BY due_date ASC
            """.format(days))
            
            rows = await cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
