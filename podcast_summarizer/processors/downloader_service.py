"""
Service for downloading podcast episodes using the downloader module.
"""
import concurrent.futures
import uuid
import os
from pathlib import Path
from typing import List, Optional

from ..core.logging_config import get_logger
from ..core.config import get_settings
from ..core.azure_storage import get_storage
from .downloader import parse_feed, download_episode
from .audio import convert_to_mp3

logger = get_logger(__name__)
settings = get_settings()

def download_podcast(
    feed_url: str, 
    output_dir: Optional[Path] = None, 
    limit: Optional[int] = None, 
    concurrent_downloads: Optional[int] = None,
    use_azure_storage: bool = True
) -> List[Path]:
    """
    Download podcast episodes from an RSS feed.
    
    Args:
        feed_url: URL of the podcast RSS feed
        output_dir: Directory to save downloaded files (None for default)
        limit: Maximum number of episodes to download (None for all)
        concurrent_downloads: Number of concurrent downloads (None for default)
        use_azure_storage: Whether to upload files to Azure Blob Storage
        
    Returns:
        List of paths to downloaded files (local paths, even if uploaded to Azure)
    """
    try:
        logger.info(f"Starting download for feed: {feed_url}")
        
        # Use temp directory if none provided
        if output_dir is None:
            # Use a unique ID for this batch to prevent collisions
            batch_id = str(uuid.uuid4())[:8]
            output_dir = Path(settings.TEMP_DIR) / f"download_{batch_id}"
            os.makedirs(output_dir, exist_ok=True)
            
        # Use default concurrency if none provided
        if concurrent_downloads is None:
            concurrent_downloads = settings.MAX_CONCURRENT_DOWNLOADS
            
        podcast_title, episodes = parse_feed(feed_url)
        
        # Generate a podcast ID for consistent file naming
        podcast_id = str(uuid.uuid4())
        
        # Create temporary directory for this podcast
        podcast_dir = output_dir / podcast_title
        podcast_dir.mkdir(parents=True, exist_ok=True)
        
        # Apply episode limit if specified
        if limit and limit < len(episodes):
            logger.info(f"Limiting to {limit} episodes (from {len(episodes)} available)")
            episodes = episodes[:limit]
        
        downloaded_files = []
        
        # Get Azure storage client if needed
        storage = get_storage() if use_azure_storage else None
        
        # Use ThreadPoolExecutor for concurrent downloads
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_downloads) as executor:
            future_to_episode = {}
            
            for episode in episodes:
                # Generate episode ID for consistent file naming
                episode_id = str(uuid.uuid4())
                
                # First check if this episode's audio already exists in storage
                if storage and use_azure_storage:
                    # Create a consistent blob name based on IDs
                    podcast_uuid_segment = podcast_id[:8]
                    episode_uuid_segment = episode_id[:8]
                    blob_name = f"audio/{podcast_uuid_segment}_{episode_uuid_segment}.mp3"
                    
                    if storage.blob_exists(blob_name):
                        logger.info(f"Episode '{episode.title}' already exists in storage, skipping download")
                        # Download the file from storage to local cache for processing
                        local_file = storage.download_blob(blob_name, podcast_dir / f"{podcast_uuid_segment}_{episode_uuid_segment}.mp3")
                        if local_file:
                            downloaded_files.append(local_file)
                            continue
                
                # If not found in storage or download failed, submit for download
                future = executor.submit(download_episode, episode, podcast_dir)
                future_to_episode[future] = (episode, episode_id)
            
            # Process completed downloads
            for future in concurrent.futures.as_completed(future_to_episode):
                episode, episode_id = future_to_episode[future]
                try:
                    file_path = future.result()
                    if file_path:
                        # Convert to MP3 if not already
                        mp3_path = convert_to_mp3(file_path)
                        
                        # Upload to Azure Blob Storage if requested
                        if use_azure_storage and storage:
                            try:
                                # Create a blob name with podcast/episode UUIDs for consistent naming
                                podcast_uuid_segment = podcast_id[:8]
                                episode_uuid_segment = episode_id[:8]
                                blob_name = f"audio/{podcast_uuid_segment}_{episode_uuid_segment}.mp3"
                                
                                # Upload the file
                                blob_url = storage.upload_file(mp3_path, blob_name)
                                logger.info(f"Uploaded {mp3_path} to Azure Blob Storage: {blob_url}")
                            except Exception as e:
                                logger.error(f"Failed to upload {mp3_path} to Azure Blob Storage: {str(e)}")
                        
                        downloaded_files.append(Path(mp3_path))
                except Exception as e:
                    logger.error(f"Error processing {episode.title}: {e}")
        
        logger.info(f"Downloaded {len(downloaded_files)} out of {len(episodes)} episodes from {podcast_title}")
        return downloaded_files
        
    except Exception as e:
        logger.error(f"Error downloading podcast: {str(e)}")
        return []
