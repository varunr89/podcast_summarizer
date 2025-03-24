"""
Functions for parsing podcast RSS feeds.
"""
import feedparser
import cloudscraper
from io import BytesIO
from datetime import datetime
from typing import Dict, Any, Optional, Literal

from ..core.logging_config import get_logger

logger = get_logger(__name__)

# Try to import the crawler-based parser
try:
    from .crawler_feed_parser import parse_podcast_site
    CRAWLER_AVAILABLE = True
except ImportError:
    logger.warning("crawler_feed_parser module not available. Installing crawl4ai package is recommended.")
    CRAWLER_AVAILABLE = False

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

def parse_podcast(url: str, parser_type: Literal["rss", "crawler", "auto"] = "auto") -> Dict[str, Any]:
    """
    Parse a podcast using the specified method.
    
    Args:
        url: URL of the podcast (RSS feed or website)
        parser_type: Type of parser to use ("rss", "crawler", or "auto")
        
    Returns:
        Dictionary with podcast metadata and episodes
    """
    logger.info(f"Parsing podcast from {url} using {parser_type} parser")
    
    # Determine parser type if auto
    if parser_type == "auto":
        if ".xml" in url.lower() or "feed" in url.lower() or "rss" in url.lower():
            parser_type = "rss"
        else:
            parser_type = "crawler" if CRAWLER_AVAILABLE else "rss"
    
    # Parse based on type
    if parser_type == "crawler" and CRAWLER_AVAILABLE:
        try:
            return parse_podcast_site(url)
        except Exception as e:
            logger.warning(f"Crawler parser failed ({str(e)}), falling back to RSS parser")
            return parse_podcast_feed(url)
    else:
        return parse_podcast_feed(url)
