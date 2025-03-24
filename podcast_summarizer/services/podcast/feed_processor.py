"""
Functions for downloading and processing podcast feeds.
"""
import uuid
from pathlib import Path

from ...core.logging_config import get_logger
from ...processors.episode_processor import download_podcast_episodes

logger = get_logger(__name__)

def download_episodes_from_feed(request, temp_dir):
    """Download episodes from a podcast feed."""
    # Download episodes
    temp_files = download_podcast_episodes(request.feed_url, temp_dir)
    
    # Filter episodes
    if request.episode_indices and temp_files:
        selected_files = []
        for idx in request.episode_indices:
            idx_zero_based = idx - 1
            if 0 <= idx_zero_based < len(temp_files):
                selected_files.append(temp_files[idx_zero_based])
            else:
                logger.warning(f"Episode index {idx} is out of range (1-{len(temp_files)})")
        temp_files = selected_files
    elif request.limit_episodes:
        temp_files = temp_files[:request.limit_episodes]
    
    # Create episode data objects
    episode_data = []
    for file in temp_files:
        logger.info(f"Processing file: {file}")
        episode_data.append({
            "id": str(uuid.uuid4()),
            "podcast_id": request.podcast_id,
            "title": Path(file).stem,
            "audio_file_path": str(file)
        })
    
    return episode_data
