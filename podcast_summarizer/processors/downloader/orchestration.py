"""Orchestration of podcast episode downloads."""

import concurrent.futures
import uuid
from pathlib import Path
from typing import List, Optional

from ...core.logging_config import get_logger
from ...processors.audio import convert_to_mp3
from .episode import Episode, parse_feed
from .download_methods import (
    download_with_headers,
    download_with_wget,
    download_with_youtube_dl,
    download_with_selenium
)

logger = get_logger(__name__)

def download_episode(episode: Episode, output_dir: Path) -> Optional[Path]:
    """Try multiple download methods in sequence until one succeeds."""
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Try different download methods in order of complexity
    methods = [
        download_with_headers,
        download_with_wget,
        download_with_youtube_dl,
        download_with_selenium
    ]
    
    for method in methods:
        logger.info(f"Trying download method: {method.__name__}")
        result = method(episode, output_dir)
        if result:
            return result
    
    logger.error(f"All download methods failed for {episode.title}")
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
