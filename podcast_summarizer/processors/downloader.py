"""Module for downloading podcast episodes from RSS feeds."""
import concurrent.futures
import uuid
from pathlib import Path
from typing import List,Dict, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime


import feedparser
import requests
from ..core.logging_config import get_logger
from ..processors.audio import convert_to_mp3

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

def download_episode(episode: Episode, output_dir: Path) -> Optional[Path]:
    """Download an individual podcast episode."""
    try:
        # Extract episode audio URL and download
        file_name = f"{episode.title[:30].replace('/', '_')}.audio"
        file_path = output_dir / file_name
        
        response = requests.get(episode.url, stream=True)
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        episode.file_path = file_path
        return file_path
    except Exception as e:
        logger.error(f"Failed to download {episode.title}: {e}")
        return None

def download_episodes(
    feed_url: str,
    output_dir: Path,
    limit: Optional[int] = None,
    concurrent_downloads: int = 3,
    storage = None
) -> List[Path]:
    """Download multiple podcast episodes concurrently."""
    podcast_title, episodes = parse_feed(feed_url)
    podcast_id = str(uuid.uuid4())
    
    # Create podcast directory
    podcast_dir = output_dir / podcast_title
    podcast_dir.mkdir(parents=True, exist_ok=True)
    
    # Apply episode limit
    if limit and limit < len(episodes):
        episodes = episodes[:limit]
    
    downloaded_files = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_downloads) as executor:
        futures = {executor.submit(download_episode, ep, podcast_dir): ep for ep in episodes}
        
        for future in concurrent.futures.as_completed(futures):
            try:
                file_path = future.result()
                if file_path:
                    # Convert to MP3
                    mp3_path = convert_to_mp3(file_path)
                    
                    # Upload to storage if needed
                    if storage:
                        episode_id = str(uuid.uuid4())
                        blob_name = f"audio/{podcast_id[:8]}_{episode_id[:8]}.mp3"
                        storage.upload_file(mp3_path, blob_name)
                    
                    downloaded_files.append(Path(mp3_path))
            except Exception as e:
                logger.error(f"Processing error: {e}")
    
    return downloaded_files
