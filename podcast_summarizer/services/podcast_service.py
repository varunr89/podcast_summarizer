"""
Service for processing podcast episodes, including downloading, transcribing, and managing storage.
"""
import os
from pathlib import Path

from ..api.models import PodcastFeedRequest
from ..core.database import get_db
from ..core.logging_config import get_logger
from ..core.azure_storage import get_storage
from ..core.config import get_settings
from ..processors.episode_processor import cleanup_resources

# Import functions from refactored modules
from .podcast.episode_data import get_episode_data, filter_episodes
from .podcast.feed_processor import download_episodes_from_feed
from .podcast.episode_processor import process_single_episode
from .podcast.transcript_handler import (
    get_existing_transcript, 
    save_transcription, 
    fetch_publisher_transcript
)

logger = get_logger(__name__)
settings = get_settings()

def process_podcast_task(request: PodcastFeedRequest, job_id: str):
    """
    Background task to process a podcast feed, download episodes, and generate transcriptions.
    """
    try:
        # Create a unique temp directory for this job
        temp_dir = Path(settings.TEMP_DIR) / f"job_{job_id[:8]}"
        os.makedirs(temp_dir, exist_ok=True)
        logger.info(f"Starting podcast processing task with job ID: {job_id} using temp dir: {temp_dir}")
        
        # Get dependencies
        storage = get_storage()
        db = get_db()
        podcast_id = request.podcast_id
        
        # Get episode data
        episode_data = get_episode_data(request, podcast_id, db, temp_dir)
        
        # Process each episode
        for episode in episode_data:
            process_single_episode(
                episode, 
                podcast_id, 
                temp_dir, 
                storage, 
                db, 
                split_size_mb=100,  # Example split size
                keep_audio_files=False
            )
            
        logger.info(f"Job {job_id} completed: processed {len(episode_data)} episodes.")
        
        # Cleanup
        if not settings.CACHE_TEMP_FILES:
            cleanup_resources(temp_dir)
        
    except Exception as e:
        logger.error(f"Error in processing podcast: {str(e)}", exc_info=True)

# Re-export functions for backward compatibility
__all__ = [
    'process_podcast_task',
    'get_episode_data',
    'filter_episodes',
    'download_episodes_from_feed',
    'process_single_episode',
    'get_existing_transcript',
    'save_transcription',
    'fetch_publisher_transcript'
]