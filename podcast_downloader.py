#!/usr/bin/env python3
"""
Podcast Downloader

A simple and robust tool to download podcast episodes from RSS feeds.
"""
import argparse
import concurrent.futures
import feedparser
import logging
import requests
import sys
from dataclasses import dataclass
from pathlib import Path
from time import time
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("podcast_downloader")


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
        feed = feedparser.parse(feed_url)
        
        if feed.get("bozo_exception"):
            raise ValueError(f"Invalid feed: {feed.bozo_exception}")
            
        if not feed.entries:
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
        
        if not episodes:
            raise ValueError("No audio content found in feed")
            
        return podcast_title, episodes
        
    except Exception as e:
        logger.error(f"Error parsing feed: {e}")
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


def download_podcast(
    feed_url: str, 
    output_base_dir: Path, 
    limit: Optional[int] = None, 
    concurrent_downloads: int = 3
) -> List[Path]:
    """
    Download podcast episodes from an RSS feed.
    
    Args:
        feed_url: URL of the podcast RSS feed
        output_base_dir: Base directory to save downloaded files
        limit: Maximum number of episodes to download (None for all)
        concurrent_downloads: Number of concurrent downloads
        
    Returns:
        List of paths to downloaded files
    """
    try:
        podcast_title, episodes = parse_feed(feed_url)
        
        # Create directory for this podcast
        podcast_dir = output_base_dir / podcast_title
        podcast_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Found {len(episodes)} episodes in feed")
        
        # Apply episode limit if specified
        if limit and limit < len(episodes):
            logger.info(f"Limiting to {limit} episodes")
            episodes = episodes[:limit]
        
        downloaded_files = []
        
        # Use ThreadPoolExecutor for concurrent downloads
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_downloads) as executor:
            future_to_episode = {
                executor.submit(download_episode, episode, podcast_dir): episode
                for episode in episodes
            }
            
            for future in concurrent.futures.as_completed(future_to_episode):
                episode = future_to_episode[future]
                try:
                    file_path = future.result()
                    if file_path:
                        downloaded_files.append(file_path)
                except Exception as e:
                    logger.error(f"Error downloading {episode.title}: {e}")
        
        return downloaded_files
        
    except ValueError as e:
        logger.error(str(e))
        return []


def main() -> None:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Download podcast episodes from RSS feeds",
        epilog="Example: podcast_downloader.py https://example.com/podcast.xml -o ./podcasts -l 5"
    )
    parser.add_argument(
        "feed_urls", 
        nargs="+", 
        help="URLs of podcast RSS feeds"
    )
    parser.add_argument(
        "-o", "--output-dir", 
        default="./podcasts", 
        help="Directory to save downloaded files (default: ./podcasts)"
    )
    parser.add_argument(
        "-l", "--limit", 
        type=int, 
        help="Maximum number of episodes to download per feed"
    )
    parser.add_argument(
        "-c", "--concurrent", 
        type=int, 
        default=3,
        help="Number of concurrent downloads (default: 3)"
    )
    parser.add_argument(
        "-v", "--verbose", 
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Set logging level based on verbosity
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    output_dir = Path(args.output_dir)
    
    total_downloads = 0
    for feed_url in args.feed_urls:
        try:
            downloaded = download_podcast(
                feed_url, 
                output_dir, 
                limit=args.limit,
                concurrent_downloads=args.concurrent
            )
            total_downloads += len(downloaded)
        except Exception as e:
            logger.error(f"Error processing feed {feed_url}: {e}")
    
    logger.info(f"Downloaded {total_downloads} episodes in total")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Download interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)