"""
MIT Deadline Scraper for Sir Tim the Timely

Scrapes deadline information from MIT's first-year website and updates the database.
"""

import logging
import re
import asyncio
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString

from .database import DatabaseManager

logger = logging.getLogger("sir_tim.scraper")

class MITDeadlineScraper:
    """Scrapes MIT deadline information from the official website."""
    
    def __init__(self, base_url: str, db_manager: DatabaseManager, ai_handler=None):
        self.base_url = base_url
        self.db_manager = db_manager
        self.ai_handler = ai_handler
        self.session: Optional[aiohttp.ClientSession] = None
        self.scrape_interval_hours = int(os.getenv("SCRAPE_INTERVAL_HOURS", "6"))
        
        # Regex patterns for date parsing
        self.date_patterns = [
            r'(\w+)\s+(\d+)',  # "June 4", "July 1"
            r'(\w+)\s+(\d+),?\s+(\d{4})',  # "June 4, 2025"
            r'(\w+)\s+(\d+)\s*[-–]\s*(\w+)\s+(\d+)',  # "June 5 - June 13"
        ]
        
        # Month name mappings
        self.months = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12,
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        
        # Category keywords for classification
        self.category_keywords = {
            'Medical': ['medical', 'health', 'vaccination', 'immunization'],
            'Academic': ['academic', 'transcript', 'fee', 'essay', 'test', 'exam', 'ap', 'ib'],
            'Housing': ['housing', 'residence', 'room', 'dorm'],
            'Financial': ['tuition', 'payment', 'bill', 'financial', 'meal plan'],
            'Orientation': ['orientation', 'fpop', 'pre-orientation', 'arrival'],
            'Administrative': ['emergency contact', 'websis', 'kerberos', 'id photo'],
            'Registration': ['registration', 'sign up', 'application']
        }
    
    async def start_periodic_scraping(self):
        """Start the periodic scraping task."""
        logger.info("Starting periodic scraping - first scrape will begin immediately")
        while True:
            try:
                await self.scrape_deadlines()
                logger.info(f"Sleeping for {self.scrape_interval_hours} hours until next scrape")
                await asyncio.sleep(self.scrape_interval_hours * 3600)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic scraping: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour before retrying
    
    async def scrape_deadlines(self) -> List[Dict]:
        """Scrape deadlines from the MIT website."""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            logger.info(f"Scraping deadlines from {self.base_url}")
            
            async with self.session.get(self.base_url) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}: Failed to fetch deadline page")
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                deadlines = await self._parse_deadlines(soup)
                
                # Enhance all titles in a single batch API call if AI handler is available
                if self.ai_handler and deadlines:
                    try:
                        logger.info(f"Enhancing {len(deadlines)} deadline titles with AI...")
                        enhanced_titles = await self.ai_handler.enhance_deadline_titles_batch(deadlines)
                        
                        # Apply enhanced titles back to deadlines
                        for deadline in deadlines:
                            original_title = deadline['title']
                            if original_title in enhanced_titles:
                                deadline['title'] = enhanced_titles[original_title]
                        
                        logger.info(f"Successfully enhanced {len(enhanced_titles)} titles")
                    except Exception as e:
                        logger.warning(f"Batch title enhancement failed, using original titles: {e}")
                
                await self._update_database(deadlines)
                
                logger.info(f"Successfully scraped {len(deadlines)} deadlines")
                return deadlines
                
        except Exception as e:
            logger.error(f"Failed to scrape deadlines: {e}")
            raise
    
    async def _parse_deadlines(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse deadlines from the HTML soup."""
        deadlines = []
        current_year = datetime.now().year
        
        # Find all sections (May, June, July, etc.)
        sections = soup.find_all(['h3', 'h4'], string=re.compile(r'(May|June|July|August|September|October|November|December)', re.IGNORECASE))
        
        for section in sections:
            month_name = section.get_text().strip()
            month_num = self._parse_month(month_name)
            if not month_num:
                continue
            # Look for the next <ul> sibling containing list items
            sibling = section.find_next_sibling()
            # Find the next UL tag
            ul = None
            while sibling:
                if isinstance(sibling, Tag) and sibling.name == 'ul':
                    ul = sibling
                    break
                sibling = sibling.find_next_sibling()
            if not ul:
                continue
            # Process each list item
            for li in ul.find_all('li'):
                if not isinstance(li, Tag):
                    continue
                text = li.get_text().strip()
                info = await self._extract_deadline_info(text, month_num, current_year)
                if not info:
                    continue
                # Attach first link if present
                link = li.find('a')
                if isinstance(link, Tag):
                    href = link.get('href')
                    if href:
                        info['url'] = urljoin(self.base_url, href)
                deadlines.append(info)
        
        return deadlines
    
    def _parse_month(self, month_text: str) -> Optional[int]:
        """Parse month number from month text."""
        month_text = month_text.lower().strip()
        return self.months.get(month_text)
    
    async def _extract_deadline_info(self, text: str, month: int, year: int) -> Optional[Dict]:
        """Extract deadline information from text."""
        # Skip empty or very short text
        if not text or len(text.strip()) < 10:
            return None
        
        # Look for date patterns in the text
        for pattern in self.date_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                try:
                    groups = match.groups()
                    # Parse end date
                    due_date = self._parse_date_from_match(match, month, year)
                    # Determine if this is an event with a range
                    if len(groups) == 4:
                        # Parse start date
                        start_month = self._parse_month(groups[0]) or month
                        start_day = int(groups[1])
                        start_date = datetime(year, start_month, start_day, 0, 0, 0)
                        is_event = True
                    else:
                        start_date = None
                        is_event = False
                    if due_date:
                        # Extract title and description
                        title, description = self._extract_title_description(text, match)
                        # Determine category and criticality
                        category = self._categorize_deadline(text)
                        is_critical = self._is_critical_deadline(text)
                        
                        # Note: AI enhancement will be done in batch after all deadlines are collected
                        
                        return {
                            'title': title,
                            'description': description,
                            'start_date': start_date,
                            'due_date': due_date,
                            'category': category,
                            'is_critical': is_critical,
                            'is_event': is_event,
                            'url': None  # Will be set by caller if found
                        }
                except Exception as e:
                    logger.debug(f"Failed to parse date from match {match.group()}: {e}")
                    continue
        
        return None
    
    def _parse_date_from_match(self, match, default_month: int, year: int) -> Optional[datetime]:
        """Parse datetime from regex match."""
        groups = match.groups()
        
        try:
            if len(groups) == 2:  # "Month Day" format
                month_str, day_str = groups
                month = self._parse_month(month_str) or default_month
                day = int(day_str)
                
                return datetime(year, month, day, 23, 59, 59)  # End of day
                
            elif len(groups) == 3:  # "Month Day, Year" format
                month_str, day_str, year_str = groups
                month = self._parse_month(month_str) or default_month
                day = int(day_str)
                year = int(year_str)
                
                return datetime(year, month, day, 23, 59, 59)
                
            elif len(groups) == 4:  # "Month Day - Month Day" format
                # Use the end date
                month_str, day_str, end_month_str, end_day_str = groups
                month = self._parse_month(end_month_str) or default_month
                day = int(end_day_str)
                
                return datetime(year, month, day, 23, 59, 59)
                
        except (ValueError, TypeError) as e:
            logger.debug(f"Error parsing date from groups {groups}: {e}")
            return None
        
        return None
    
    def _extract_title_description(self, text: str, date_match) -> tuple[str, str]:
        """Extract title and description from deadline text."""
        # Split text into sentences
        sentences = re.split(r'[.!?]+', text)
        
        # Find the sentence containing the date
        date_sentence = ""
        other_sentences = []
        
        for sentence in sentences:
            if date_match.group() in sentence:
                date_sentence = sentence.strip()
            else:
                cleaned = sentence.strip()
                if cleaned:
                    other_sentences.append(cleaned)
        
        # Create title from date sentence
        title = date_sentence
        if len(title) > 100:
            title = title[:97] + "..."
        
        # Create description from remaining sentences
        description = ". ".join(other_sentences)
        if len(description) > 500:
            description = description[:497] + "..."
        
        return title or "MIT Deadline", description
    
    def _categorize_deadline(self, text: str) -> str:
        """Categorize deadline based on keywords."""
        text_lower = text.lower()
        
        for category, keywords in self.category_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return category
        
        return "General"
    
    def _is_critical_deadline(self, text: str) -> bool:
        """Determine if deadline is critical based on keywords."""
        critical_keywords = [
            'must', 'required', 'mandatory', 'deadline', 'due',
            'final', 'important', 'critical', 'essential'
        ]
        
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in critical_keywords)
    
    async def _find_recurring_deadline(self, deadline_data: Dict) -> Optional[Dict]:
        """Find if this deadline is a recurring one that already exists in the database."""
        # Get the normalized title for comparison
        normalized_title = self._normalize_deadline_title(deadline_data['title'])
        
        # Search for existing deadlines with similar titles
        all_deadlines = await self.db_manager.get_deadlines(active_only=False)
        
        for existing in all_deadlines:
            existing_normalized = self._normalize_deadline_title(existing['title'])
            
            # Check if titles match after normalization
            if existing_normalized == normalized_title:
                # Additional checks to confirm it's the same recurring deadline
                if (existing['category'] == deadline_data['category'] and
                    self._is_similar_description(existing.get('description', ''), 
                                               deadline_data.get('description', ''))):
                    return existing
        
        return None
    
    def _normalize_deadline_title(self, title: str) -> str:
        """Normalize deadline title by removing date-specific information."""
        import re
        
        # Remove common date patterns from titles
        title = re.sub(r'\b\w+\s+\d+\b', '', title)  # Remove "June 15", "July 1", etc.
        title = re.sub(r'\b\d+\s*[-–]\s*\d+\b', '', title)  # Remove "15-20", "1-5", etc.
        title = re.sub(r'\b\d{4}\b', '', title)  # Remove years like "2024", "2025"
        title = re.sub(r'\b(by|due|before|after)\s+\w+\s+\d+\b', '', title, flags=re.IGNORECASE)
        
        # Remove extra whitespace and normalize
        title = ' '.join(title.split())
        title = title.strip(' ,-–')
        
        return title.lower()
    
    def _is_similar_description(self, desc1: str, desc2: str) -> bool:
        """Check if two descriptions are similar enough to be the same recurring deadline."""
        if not desc1 and not desc2:
            return True
        if not desc1 or not desc2:
            return False
        
        # Simple similarity check - remove dates and compare
        import re
        
        def clean_description(desc):
            # Remove dates and normalize
            desc = re.sub(r'\b\w+\s+\d+(?:,\s*\d{4})?\b', '', desc)
            desc = re.sub(r'\b\d+\s*[-–]\s*\d+\b', '', desc)
            return ' '.join(desc.split()).lower()
        
        clean1 = clean_description(desc1)
        clean2 = clean_description(desc2)
        
        # Consider similar if 80% of words match
        words1 = set(clean1.split())
        words2 = set(clean2.split())
        
        if not words1 and not words2:
            return True
        if not words1 or not words2:
            return False
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        similarity = intersection / union if union > 0 else 0
        return similarity >= 0.8
    
    async def _update_database(self, deadlines: List[Dict]):
        """Update database with scraped deadlines, handling recurring deadlines intelligently."""
        updated_count = 0
        added_count = 0
        skipped_count = 0
        
        for deadline_data in deadlines:
            try:
                # Check for recurring deadline patterns first
                recurring_match = await self._find_recurring_deadline(deadline_data)
                
                if recurring_match:
                    # This is a recurring deadline - update the existing one
                    deadline_id = recurring_match['id']
                    
                    # Only update if the new due date is different and in the future
                    existing_due = datetime.fromisoformat(recurring_match['due_date'].replace('Z', '+00:00'))
                    new_due = deadline_data['due_date']
                    
                    if new_due > existing_due:
                        await self.db_manager.update_deadline(deadline_id, **deadline_data)
                        updated_count += 1
                        logger.info(f"Updated recurring deadline: {deadline_data['title']}")
                    else:
                        skipped_count += 1
                        logger.debug(f"Skipped recurring deadline (not newer): {deadline_data['title']}")
                else:
                    # Check for exact duplicates
                    existing = await self.db_manager.search_deadlines(deadline_data['title'][:50])
                    exact_match = None
                    
                    if existing:
                        # Look for exact match by title, category, and similar due date (within 7 days)
                        for item in existing:
                            if (item['title'] == deadline_data['title'] and 
                                item['category'] == deadline_data['category']):
                                existing_due = datetime.fromisoformat(item['due_date'].replace('Z', '+00:00'))
                                new_due = deadline_data['due_date']
                                if abs((existing_due - new_due).days) <= 7:
                                    exact_match = item
                                    break
                    
                    if exact_match:
                        # Update existing exact match
                        deadline_id = exact_match['id']
                        await self.db_manager.update_deadline(deadline_id, **deadline_data)
                        updated_count += 1
                    else:
                        # Add new deadline
                        await self.db_manager.add_deadline(**deadline_data)
                        added_count += 1
                    
            except Exception as e:
                logger.error(f"Failed to update deadline {deadline_data.get('title', 'Unknown')}: {e}")
        
        logger.info(f"Database updated: {added_count} added, {updated_count} updated, {skipped_count} skipped (recurring)")
    
    async def close(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.close()
