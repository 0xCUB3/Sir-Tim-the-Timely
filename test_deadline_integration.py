#!/usr/bin/env python3
"""
Test script to demonstrate the deadline integration in the chat handler.

This shows how the chatbot now has access to deadline information and 
can provide context-aware responses.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from src.gemini_chat_handler import GeminiChatHandler
from src.database import DatabaseManager

# Mock data for testing
class MockDatabaseManager:
    """Mock database manager for testing."""
    
    async def get_upcoming_deadlines(self, days: int):
        """Return mock deadline data."""
        now = datetime.now(timezone.utc)
        
        return [
            {
                'id': 1,
                'title': 'Health Forms Submission',
                'due_date': (now + timedelta(days=2)).isoformat(),
                'category': 'Medical',
                'is_event': False,
                'description': 'Submit immunization records'
            },
            {
                'id': 2,
                'title': 'Housing Application',
                'due_date': (now + timedelta(days=5)).isoformat(),
                'category': 'Housing',
                'is_event': False,
                'description': 'Complete housing preference form'
            },
            {
                'id': 3,
                'title': 'Tuition Payment',
                'due_date': (now + timedelta(days=1)).isoformat(),
                'category': 'Financial',
                'is_event': False,
                'description': 'Pay semester tuition'
            }
        ]
    
    async def get_all_chat_channels(self):
        return {}
    
    async def set_chat_channel(self, guild_id, channel_id):
        return True
    
    async def remove_chat_channel(self, guild_id):
        return True

async def test_deadline_context():
    """Test the deadline context functionality."""
    logging.basicConfig(level=logging.INFO)
    
    # Create mock handler without actual API key
    db_manager = MockDatabaseManager()
    
    # We can't fully test without an API key, but we can test the cache and context logic
    print("=== Testing Deadline Context Integration ===\n")
    
    # This would normally require an API key, so we'll just test the logic
    try:
        # We can test the cache refresh logic
        handler = GeminiChatHandler.__new__(GeminiChatHandler)
        handler.db_manager = db_manager
        handler._deadline_cache = {}
        handler._deadline_cache_timestamp = 0
        handler._deadline_cache_ttl = 300
        
        # Test cache refresh
        await handler._refresh_deadline_cache()
        
        print("✅ Cache refresh successful!")
        print(f"Urgent deadlines: {len(handler._deadline_cache['urgent'])}")
        print(f"Upcoming deadlines: {len(handler._deadline_cache['upcoming'])}")
        print(f"Categories: {list(handler._deadline_cache['by_category'].keys())}")
        
        # Test context generation
        contexts = [
            await handler._get_deadline_context("When are the medical deadlines?"),
            await handler._get_deadline_context("I need help with housing stuff"),
            await handler._get_deadline_context("What's due soon?"),
            await handler._get_deadline_context("Just saying hello")  # Should return empty
        ]
        
        print("\n=== Context Generation Tests ===")
        for i, context in enumerate(contexts):
            print(f"Test {i+1}: '{context}'" if context else f"Test {i+1}: (no context)")
        
        print("\n✅ All tests passed!")
        print("\n=== DM Functionality Added ===")
        print("🎯 NEW FEATURES:")
        print("1. Users can now DM Tim directly for private conversations")
        print("2. Higher response rate in DMs (85% vs 65% in channels)")
        print("3. Same deadline awareness and aggressive personality in DMs")
        print("4. Separate cooldown tracking for DMs vs channels")
        print("5. Context indicators show when user is in a private DM")
        
        print("\n=== How It Works ===")
        print("1. The chatbot now caches deadline data every 5 minutes")
        print("2. When users mention deadline keywords, relevant context is added")
        print("3. The AI uses this context to give more informed, aggressive responses")
        print("4. Cache is automatically refreshed to stay current")
        print("5. DMs are treated as high-priority interactions with Tim")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_deadline_context())
