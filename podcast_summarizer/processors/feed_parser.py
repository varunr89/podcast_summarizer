"""
Functions for parsing podcast RSS feeds.
"""
import feedparser
import cloudscraper
from io import BytesIO
from datetime import datetime
from typing import Dict, Any

from ..core.logging_config import get_logger

logger = get_logger(__name__)

def parse_podcast_feed(feed_url: str) -> Dict[str, Any]:
    """
    Parse a podcast RSS feed and extract relevant metadata.
    
    Args:
        feed_url: URL of the podcast RSS feed
        
    Returns:
        Dictionary with podcast metadata and episodes
    """
    try:
        scraper = cloudscraper.create_scraper()
        content = scraper.get(feed_url).content
        feed = feedparser.parse(BytesIO(content))
        if not feed.entries:
            raise ValueError("No entries found in feed")
        
        # Extract podcast metadata
        podcast_data = {
            "title": feed.feed.title,
            "description": feed.feed.description if hasattr(feed.feed, "description") else "",
            "author": feed.feed.author if hasattr(feed.feed, "author") else "",
            "artwork_url": feed.feed.image.href if hasattr(feed.feed, "image") and hasattr(feed.feed.image, "href") else "",
            "feed_url": feed_url,
            "last_fetched_at": datetime.now().isoformat(),
        }
        
        # Extract episodes data
        episodes = []
        for entry in feed.entries:
            episode = {
                "title": entry.title,
                "description": entry.description if hasattr(entry, "description") else "",
                "published_at": entry.published if hasattr(entry, "published") else "",
                "audio_url": next((link.href for link in entry.links if hasattr(link, "type") and "audio" in link.type), "")
                if hasattr(entry, "links") else ""
            }
            episodes.append(episode)
        
        return {"podcast": podcast_data, "episodes": episodes}
    except Exception as e:
        logger.error(f"Error parsing podcast feed: {str(e)}", exc_info=True)
        raise ValueError(f"Failed to parse podcast feed: {str(e)}")
