"""
AI Handler for Sir Tim the Timely

Handles natural language processing and queries using Google's Gemini API.
"""

import logging
import os
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

from .database import DatabaseManager

logger = logging.getLogger("sir_tim.ai")

try:
    import google.generativeai as genai
    from google.generativeai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("Google Generative AI library not available")

class AIHandler:
    """Handles AI-powered natural language queries about deadlines."""
    
    def __init__(self, api_key: str, db_manager: DatabaseManager):
        self.db_manager = db_manager
        
        if not GEMINI_AVAILABLE:
            raise ImportError("Google Generative AI library not available. Install with: pip install google-generativeai")
        
        # Configure Gemini API
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        # System prompt for deadline queries
        self.system_prompt = """
You are Sir Tim the Timely, a helpful assistant for MIT first-year students tracking deadlines.

Your role is to help students understand and manage their MIT admission and orientation deadlines.
You have access to a database of current deadlines and can answer questions about:
- When things are due
- What tasks need to be completed
- How to complete various requirements
- Deadline priorities and urgency

Key guidelines:
1. Be friendly, helpful, and encouraging
2. Provide specific dates and details when available
3. Include relevant links when mentioning deadlines
4. Remind students to check official MIT sources for the most current information
5. Use a slightly formal but warm tone
6. If you don't have specific information, say so and suggest where to find it

Current date context: {current_date}

Available deadline categories: Medical, Academic, Housing, Financial, Orientation, Administrative, Registration, General
"""
        
        logger.info("AI Handler initialized with Gemini 1.5 Flash")
    
    async def process_natural_query(self, query: str, user_context: Optional[Dict] = None) -> str:
        """Process a natural language query about deadlines."""
        try:
            # Get relevant deadlines from database
            relevant_deadlines = await self._get_relevant_deadlines(query)
            
            # Build context for the AI
            context = await self._build_context(relevant_deadlines, user_context)
            
            # Format the prompt
            prompt = self._format_prompt(query, context)
            
            # Generate response
            response = await self._generate_response(prompt)
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing natural query: {e}")
            return "I apologize, but I'm having trouble processing your request right now. Please try asking about specific deadlines or check the MIT first-year website directly."
    
    async def summarize_upcoming_deadlines(self, days: int = 7) -> str:
        """Generate a summary of upcoming deadlines."""
        try:
            deadlines = await self.db_manager.get_upcoming_deadlines(days)
            
            if not deadlines:
                return f"Great news! You don't have any deadlines in the next {days} days. 🎉"
            
            context = {
                'deadlines': deadlines,
                'timeframe': f"{days} days",
                'current_date': datetime.now().strftime("%B %d, %Y")
            }
            
            prompt = f"""
Based on the following upcoming MIT deadlines, create a helpful summary for a first-year student:

{self._format_deadlines_for_prompt(deadlines)}

Create a friendly, organized summary that:
1. Groups deadlines by urgency (this week vs next week)
2. Highlights the most critical items
3. Provides encouraging but clear guidance
4. Includes specific dates and times
5. Suggests prioritization

Use a warm, helpful tone and include relevant emojis.
"""
            
            response = await self._generate_response(prompt)
            return response
            
        except Exception as e:
            logger.error(f"Error summarizing deadlines: {e}")
            return "I'm having trouble accessing your deadline information right now. Please try again later."
    
    async def explain_deadline_category(self, category: str) -> str:
        """Explain what a specific deadline category involves."""
        try:
            deadlines = await self.db_manager.get_deadlines(category=category)
            
            prompt = f"""
Explain the "{category}" category of MIT first-year deadlines to a new student.

Current deadlines in this category:
{self._format_deadlines_for_prompt(deadlines)}

Provide:
1. What this category generally covers
2. Why these deadlines are important
3. Common questions students have
4. Tips for staying on track
5. What happens if deadlines are missed

Be helpful, informative, and reassuring.
"""
            
            response = await self._generate_response(prompt)
            return response
            
        except Exception as e:
            logger.error(f"Error explaining category {category}: {e}")
            return f"I couldn't retrieve information about {category} deadlines right now. Please check the MIT first-year website for detailed information about this category."
    
    async def suggest_deadline_priorities(self, user_id: int) -> str:
        """Suggest deadline priorities for a specific user."""
        try:
            # Get user's deadline status
            user_deadlines = await self.db_manager.get_user_deadline_status(user_id)
            all_deadlines = await self.db_manager.get_upcoming_deadlines(30)
            
            # Filter out completed deadlines
            incomplete_deadlines = []
            completed_ids = {ud['deadline_id'] for ud in user_deadlines if ud['completed']}
            
            for deadline in all_deadlines:
                if deadline['id'] not in completed_ids:
                    incomplete_deadlines.append(deadline)
            
            if not incomplete_deadlines:
                return "Congratulations! You're all caught up on your deadlines! 🎉"
            
            prompt = f"""
Based on these incomplete MIT deadlines for a first-year student, suggest priorities:

{self._format_deadlines_for_prompt(incomplete_deadlines)}

Create a prioritized action plan that:
1. Identifies the most urgent items (within 1-2 weeks)
2. Groups related deadlines that can be tackled together
3. Suggests a realistic timeline
4. Provides motivation and encouragement
5. Highlights any dependencies between deadlines

Be specific, actionable, and supportive.
"""
            
            response = await self._generate_response(prompt)
            return response
            
        except Exception as e:
            logger.error(f"Error suggesting priorities for user {user_id}: {e}")
            return "I'm having trouble analyzing your deadlines right now. Try using the `/deadlines next` command to see what's coming up."
    async def parse_deadline_text(self, text: str, base_url: str, current_year: int) -> Optional[Dict[str, Any]]:
        """Use LLM to parse a raw deadline/event text into structured data."""
        try:
            prompt = f"""
You are an assistant that extracts structured deadline and event data from raw text items.
For the following text, return a JSON object with fields:
- title (string)
- description (string)
- due_date (ISO format, end date for ranges)
- start_date (ISO format or null)
- is_event (boolean)
- category (one of Medical, Academic, Housing, Financial, Orientation, Administrative, Registration, General)
- is_critical (boolean)
- url (string or null)
Assume current year is {current_year}. Use base_url to complete relative URLs if any.
Text: "{text}"
Only output the JSON without any additional text.
"""
            response = await self._generate_response(prompt)
            import json
            data = json.loads(response)
            return data
        except Exception as e:
            logger.error(f"Failed to parse text via LLM: {e}")
            return None
    
    async def _get_relevant_deadlines(self, query: str) -> List[Dict]:
        """Get deadlines relevant to the query."""
        # Simple keyword-based relevance for now
        # Could be enhanced with semantic search later
        
        query_lower = query.lower()
        
        # Check for specific categories
        for category in ['medical', 'academic', 'housing', 'financial', 'orientation']:
            if category in query_lower:
                return await self.db_manager.get_deadlines(category=category.title())
        
        # Check for time-based queries
        if any(word in query_lower for word in ['this week', 'next week', 'soon', 'upcoming']):
            return await self.db_manager.get_upcoming_deadlines(14)
        
        if any(word in query_lower for word in ['this month', 'month']):
            return await self.db_manager.get_upcoming_deadlines(30)
        
        # Search for specific terms
        search_terms = []
        keywords = ['transcript', 'housing', 'medical', 'fpop', 'tuition', 'essay', 'fee', 'orientation']
        
        for keyword in keywords:
            if keyword in query_lower:
                search_terms.append(keyword)
        
        if search_terms:
            all_results = []
            for term in search_terms:
                results = await self.db_manager.search_deadlines(term)
                all_results.extend(results)
            return all_results
        
        # Default: return upcoming deadlines
        return await self.db_manager.get_upcoming_deadlines(14)
    
    async def _build_context(self, deadlines: List[Dict], user_context: Optional[Dict]) -> Dict:
        """Build context for the AI prompt."""
        context = {
            'current_date': datetime.now().strftime("%B %d, %Y"),
            'deadlines': deadlines,
            'deadline_count': len(deadlines)
        }
        
        if user_context:
            context.update(user_context)
        
        return context
    
    def _format_prompt(self, query: str, context: Dict) -> str:
        """Format the complete prompt for the AI."""
        system = self.system_prompt.format(current_date=context['current_date'])
        
        deadlines_text = self._format_deadlines_for_prompt(context['deadlines'])
        
        prompt = f"""
{system}

CURRENT DEADLINES:
{deadlines_text}

STUDENT QUESTION: {query}

Please provide a helpful, specific response that addresses the student's question using the available deadline information. If the question is outside your knowledge area, politely redirect them to official MIT resources.
"""
        
        return prompt
    
    def _format_deadlines_for_prompt(self, deadlines: List[Dict]) -> str:
        """Format deadlines for inclusion in AI prompts."""
        if not deadlines:
            return "No deadlines found in the database."
        
        formatted = []
        for deadline in deadlines:
            due_date = datetime.fromisoformat(deadline['due_date'].replace('Z', '+00:00'))
            formatted_date = due_date.strftime("%B %d, %Y")
            
            formatted.append(f"""
Title: {deadline['title']}
Due Date: {formatted_date}
Category: {deadline.get('category', 'General')}
Critical: {'Yes' if deadline.get('is_critical') else 'No'}
Description: {deadline.get('description', 'No description available')}
URL: {deadline.get('url', 'No URL available')}
""")
        
        return "\n".join(formatted)
    
    async def _generate_response(self, prompt: str) -> str:
        """Generate response using Gemini API."""
        try:
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            raise
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get the health status of the AI handler."""
        try:
            # Test the API with a simple request
            test_response = self.model.generate_content("Hello")
            return {
                'status': 'healthy',
                'model': 'gemini-1.5-flash',
                'test_successful': bool(test_response.text)
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'model': 'gemini-1.5-flash',
                'error': str(e)
            }
