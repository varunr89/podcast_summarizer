"""
Module for downloading podcast episodes from RSS feeds.
"""
import concurrent.futures
import feedparser
import requests
from dataclasses import dataclass
from pathlib import Path
from time import time
from typing import List, Optional, Tuple

from ..core.logging_config import get_logger
from ..core.config import get_settings

logger = get_logger(__name__)
settings = get_settings()

@dataclass
class Episode:
    """Represents a podcast episode with its metadata."""
    title: str
    audio_url: str
    published_date: Optional[str] = None
    file_type: str = "mp3"
    
    @property
    def safe_title(self) -> str:
        """Return a filesystem-safe version of the episode title."""
        # Replace spaces with underscores and remove special characters
        safe = "".join(c if c.isalnum() or c in "_- " else "_" for c in self.title)
        return safe[:100]  # Limit length to avoid issues with long filenames
    
    @property
    def file_extension(self) -> str:
        """Return the file extension based on the audio file type."""
        ext = self.file_type.split("/")[-1]
        return f".{ext}" if not ext.startswith(".") else ext

def parse_feed(feed_url: str) -> Tuple[str, List[Episode]]:
    """
    Parse an RSS feed and extract podcast information.
    
    Args:
        feed_url: URL of the podcast RSS feed
        
    Returns:
        Tuple containing podcast title and list of Episode objects
    
    Raises:
        ValueError: If the feed cannot be parsed or has no entries with audio
    """
    logger.info(f"Parsing feed: {feed_url}")
    
    try:
        # Convert feed_url to string to handle Pydantic HttpUrl objects
        feed_url_str = str(feed_url)
        feed = feedparser.parse(feed_url_str)
        
        if feed.get("bozo_exception"):
            logger.error(f"Invalid feed format: {feed.bozo_exception}")
            raise ValueError(f"Invalid feed: {feed.bozo_exception}")
            
        if not feed.entries:
            logger.warning(f"Feed contains no entries: {feed_url}")
            raise ValueError("Feed contains no entries")
        
        # Get podcast title, replace spaces with underscores for directory name
        podcast_title = feed.feed.get("title", "Unknown_Podcast").replace(" ", "_")
        
        # Extract episode information
        episodes = []
        for entry in feed.entries:
            for enclosure in entry.get("enclosures", []):
                if enclosure.get("type", "").startswith("audio/"):
                    episode = Episode(
                        title=entry.get("title", "Unknown_Episode"),
                        audio_url=enclosure.get("href"),
                        published_date=entry.get("published"),
                        file_type=enclosure.get("type", "audio/mp3")
                    )
                    episodes.append(episode)
                    logger.debug(f"Found episode: {episode.title}")
        
        if not episodes:
            logger.warning(f"No audio content found in feed: {feed_url}")
            raise ValueError("No audio content found in feed")
            
        logger.info(f"Found {len(episodes)} episodes in podcast '{podcast_title}'")
        return podcast_title, episodes
        
    except Exception as e:
        logger.error(f"Error parsing feed {feed_url}: {str(e)}")
        raise ValueError(f"Could not parse feed: {e}")

def handle_platform_specific_url(url: str) -> str:
    """
    Apply platform-specific modifications to audio URLs.
    Some podcast platforms require special handling.
    
    Args:
        url: Original audio URL
    
    Returns:
        Modified URL if needed, otherwise original URL
    """
    # Handle Buzzsprout URLs
    if "buzzsprout.com" in url:
        logger.debug(f"Applying Buzzsprout-specific URL handling for: {url}")
        
        # For Buzzsprout, sometimes adding a query parameter can help
        # or modifying the URL structure slightly
        if "?" not in url:
            return f"{url}?download=true"
    
    # Handle other platforms as needed
    
    return url

def download_episode(episode: Episode, output_dir: Path, max_retries: int = 3) -> Optional[Path]:
    """
    Download a podcast episode.
    
    Args:
        episode: Episode object containing episode information
        output_dir: Directory to save the downloaded file
        max_retries: Maximum number of download retries
        
    Returns:
        Path to the downloaded file or None if download failed
    """
    if not episode.audio_url:
        logger.warning(f"No audio URL for episode: {episode.title}")
        return None
        
    # Apply platform-specific URL modifications
    audio_url = handle_platform_specific_url(episode.audio_url)
    
    # Create output filename
    output_file = output_dir / f"{episode.safe_title}{episode.file_extension}"
    
    # Ensure the output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if file already exists and is not a partial download
    if output_file.exists():
        try:
            # Set headers for the HEAD request too
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "*/*",
                "Connection": "keep-alive",
                "Referer": "https://www.google.com/"
            }
            
            # Check file size via HEAD request
            head_response = requests.head(audio_url, timeout=10, headers=headers)
            expected_size = int(head_response.headers.get("content-length", 0))
            actual_size = output_file.stat().st_size
            
            # If file size is available and sizes match approximately, skip download
            if expected_size > 0 and abs(actual_size - expected_size) < 1024:  # 1KB tolerance
                logger.info(f"File already exists and is complete: {output_file}")
                return output_file
            elif expected_size == 0:
                # If content-length is not available, assume file is complete if size is reasonable
                if actual_size > 1024 * 1024:  # File is at least 1MB
                    logger.info(f"File exists with reasonable size (content-length unknown): {output_file}")
                    return output_file
                else:
                    logger.info(f"File exists but may be incomplete. Re-downloading: {output_file}")
            else:
                logger.info(f"File exists but may be incomplete. Re-downloading: {output_file}")
        except Exception as e:
            logger.warning(f"Could not verify file size, will re-download: {e}")
    
    logger.info(f"Downloading: {episode.title} from {audio_url}")
    
    for attempt in range(max_retries):
        try:
            # Set headers to mimic a browser/podcast client
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Referer": "https://www.google.com/"  # Some sites check referrer
            }
            
            # Use stream=True to avoid loading the whole file into memory
            with requests.get(audio_url, stream=True, timeout=30, headers=headers) as response:
                response.raise_for_status()
                
                total_size = int(response.headers.get("content-length", 0))
                
                # Write to a temporary file first
                temp_file = output_file.with_suffix(f"{output_file.suffix}.tmp")
                
                with open(temp_file, "wb") as f:
                    downloaded = 0
                    start_time = time()
                    
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Log progress for large files
                            if total_size > 0 and downloaded % (1024 * 1024) == 0:
                                percent = downloaded / total_size * 100
                                elapsed = time() - start_time
                                speed = downloaded / (1024 * 1024 * elapsed) if elapsed > 0 else 0
                                logger.debug(
                                    f"Progress: {percent:.1f}% ({downloaded/(1024*1024):.1f} MB) "
                                    f"at {speed:.1f} MB/s"
                                )
                
                # Rename the temp file to the final name
                temp_file.rename(output_file)
                logger.info(f"Downloaded: {output_file}")
                return output_file
                
        except requests.RequestException as e:
            logger.warning(f"Download attempt {attempt + 1}/{max_retries} failed: {e}")
            
            if "403" in str(e) and "buzzsprout.com" in audio_url:
                logger.info("Buzzsprout returned 403 Forbidden - this is common due to their download protection")
                logger.info("You may need to get the direct download URL from the podcast's website instead")
                
                # Some platforms use different URLs for their web player vs direct download
                # Here we could try to transform the URL in different ways
            if attempt == max_retries - 1:
                logger.error(f"Failed to download after {max_retries} attempts: {audio_url}")
                logger.info("Tip: For protected feeds, try subscribing in a podcast app and grab the URL from there")
                return None
                
    return None
