"""
Functions for retrieving and filtering episode data.
"""
import uuid
from pathlib import Path
import logging

from ...core.logging_config import get_logger
from ...api.models import PodcastFeedRequest

logger = get_logger(__name__)

def get_episode_data(request, podcast_id, db, temp_dir):
    """Get episode data from database or feed."""
    episode_data = []
    
    # Try to get episodes from database first
    if podcast_id:
        episodes = db.episode_manager.list(podcast_id)
        if episodes:
            episodes = filter_episodes(episodes, request)
            
            for episode in episodes:
                if "id" not in episode or not episode["id"]:
                    episode["id"] = str(uuid.uuid4())
                
                episode_data.append({
                    "id": episode.get("id"),
                    "podcast_id": podcast_id,
                    "title": episode.get("title", "Unknown Episode"),
                    "published_date": episode.get("published_at"),
                    "audio_url": episode.get("audio_url", ""),
                    "transcript_url": episode.get("transcript_url", None),
                    "publisher_transcript_url": episode.get("publisher_transcript_url", None)
                    
                })
    
    # If no episode data found, download from feed
    if not episode_data:
        from .feed_processor import download_episodes_from_feed
        episode_data = download_episodes_from_feed(request, temp_dir)
    
    return episode_data

def filter_episodes(episodes, request):
    """Filter episodes based on request parameters."""
    if request.episode_indices:
        # Filter episodes by requested indices
        selected_episodes = []
        for idx in request.episode_indices:
            idx_zero_based = idx - 1
            if 0 <= idx_zero_based < len(episodes):
                selected_episodes.append(episodes[idx_zero_based])
            else:
                logger.warning(f"Episode index {idx} is out of range (1-{len(episodes)})")
        return selected_episodes
    
    elif request.start_episode is not None:
        start_idx = max(0, request.start_episode - 1)
        if start_idx >= len(episodes):
            logger.warning(f"Start episode {request.start_episode} is out of range, using first episode")
            start_idx = 0
            
        end_idx = len(episodes)
        if request.episode_count is not None:
            end_idx = min(start_idx + request.episode_count, len(episodes))
        
        logger.info(f"Processing episodes {start_idx+1}-{end_idx} (of {len(episodes)} total episodes)")
        return episodes[start_idx:end_idx]
    
    elif request.limit_episodes:
        return episodes[:request.limit_episodes]
    
    return episodes
