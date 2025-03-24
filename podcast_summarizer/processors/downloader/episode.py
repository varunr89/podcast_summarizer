"""Episode data structures and feed parsing functionality."""

import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

import feedparser
from ...core.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class Episode:
    """Represents a podcast episode."""
    title: str
    url: str
    podcast_title: str
    guid: str
    published_date: Optional[datetime] = None
    description: Optional[str] = None
    duration: Optional[str] = None
    file_path: Optional[Path] = None
    
    @classmethod
    def from_feed_entry(cls, entry: Dict, podcast_title: str) -> 'Episode':
        """Create an Episode instance from a feedparser entry."""
        return cls(
            title=entry.get('title', 'Untitled Episode'),
            url=entry.enclosures[0].href if entry.get('enclosures') else '',
            podcast_title=podcast_title,
            guid=entry.get('id', str(uuid.uuid4())),
            published_date=datetime.fromtimestamp(entry.get('published_parsed', None)) if entry.get('published_parsed') else None,
            description=entry.get('summary', ''),
            duration=entry.get('itunes_duration', None)
        )

def parse_feed(feed_url: str) -> Tuple[str, List[Episode]]:
    """Parse a podcast RSS feed and extract episodes."""
    feed = feedparser.parse(feed_url)
    podcast_title = feed.feed.title
    episodes = [Episode.from_feed_entry(entry, podcast_title) for entry in feed.entries]
    return podcast_title, episodes
