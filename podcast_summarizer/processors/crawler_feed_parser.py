"""
Functions for parsing podcast feeds using crawl4ai.
This module provides an alternative to RSS feed parsing with support for publisher transcript URLs.
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, Optional

from crawl4ai import (
    AsyncWebCrawler,
    CrawlerRunConfig,
    JsonCssExtractionStrategy,
    CacheMode
)

from ..core.logging_config import get_logger

logger = get_logger(__name__)

# Define our crawl schema for podcast websites
PODCAST_SCHEMA = {
  "name": "Podcast Information",
  "baseSelector": "article",
  "fields": [
    {
      "name": "podcast_title",
      "selector": "h1#podcast-title",
      "type": "text"
    },
    {
      "name": "episodes",
      "selector": "div#results div.chart",
      "type": "nested_list",
      "fields": [
        {
          "name": "title",
          "selector": "strong",
          "type": "text"
        },
        {
          "name": "episode_number",
          "selector": "span[style*='font-size:small'][style*='font-weight:bold']",
          "type": "text"
        },
        {
          "name": "published_datetime",
          "selector": "time",
          "attribute": "datetime",
          "type": "attribute"
        },
        {
          "name": "publisher_transcript_url",
          "selector": "a[href*='transcript']",
          "attribute": "href",
          "type": "attribute"
        },
        {
          "name": "episode_notes",
          "selector": "div.episodenotes",
          "type": "text"
        },
        {
          "name": "audio_url",
          "selector": "audio",
          "attribute": "src",
          "type": "attribute"
        }
      ]
    }
  ]
}

async def parse_podcast_site_async(url: str) -> Dict[str, Any]:
    """
    Parse a podcast website using web crawling to extract metadata and episodes.
    
    Args:
        url: URL of the podcast website
        
    Returns:
        Dictionary with podcast metadata and episodes
    """
    try:
        extraction_strategy = JsonCssExtractionStrategy(PODCAST_SCHEMA, verbose=False)
        
        config = CrawlerRunConfig(
            page_timeout=60000,  # 60s limit
            delay_before_return_html=5,
            cache_mode=CacheMode.BYPASS,
            extraction_strategy=extraction_strategy
        )
        
        logger.info(f"Crawling podcast site: {url}")
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(url=url, config=config)
            
            if not result.success:
                logger.error(f"Crawl failed: {result.error_message}")
                raise ValueError(f"Failed to crawl podcast site: {result.error_message}")
            
            # Parse the extracted JSON
            data = json.loads(result.extracted_content)
            
            # Format the data to match our expected structure
            podcast_data = {
                "title": data[0].get("podcast_title", "Unknown Podcast"),
                "description": data[0].get("podcast_description", ""),
                "author": "",  # Not always available from crawl
                "artwork_url": "",  # Not always available from crawl
                "feed_url": url,
                "last_fetched_at": datetime.now().isoformat(),
            }
            
            # Extract episodes data
            episodes = []
            for episode in data[0].get("episodes", []):
                # Get title or use first 25 chars of episode notes if missing
                title = episode.get("title", "")
                if not title:
                  notes = episode.get("episode_notes", "")
                  title = (notes[:25] + "...") if len(notes) > 25 else notes
                  title = title or "Unknown Episode"  # Fallback if notes are also empty
                
                episode_data = {
                  "title": title,
                  "description": episode.get("episode_notes", ""),
                  "published_at": episode.get("published_datetime", datetime.now().isoformat()),
                  "audio_url": episode.get("audio_url", ""),
                  "publisher_transcript_url": episode.get("publisher_transcript_url", "")
                }
                episodes.append(episode_data)
            
            logger.info(f"Successfully extracted {len(episodes)} episodes from {url}")
            return {"podcast": podcast_data, "episodes": episodes}
            
    except Exception as e:
        logger.error(f"Error parsing podcast site: {str(e)}", exc_info=True)
        raise ValueError(f"Failed to parse podcast site: {str(e)}")

def parse_podcast_site(url: str) -> Dict[str, Any]:
    """
    Synchronous wrapper for the async parsing function.
    
    Args:
        url: URL of the podcast website
        
    Returns:
        Dictionary with podcast metadata and episodes
    """
    try:
        return asyncio.run(parse_podcast_site_async(url))
    except Exception as e:
        logger.error(f"Error in sync wrapper for podcast site parsing: {str(e)}")
        raise
