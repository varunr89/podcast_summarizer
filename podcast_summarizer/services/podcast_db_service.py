"""
Service for podcast database operations.
"""
import time
from typing import Dict, List, Any

from ..core.logging_config import get_logger
from ..core.database import get_db

logger = get_logger(__name__)

def update_existing_podcast(db, existing_podcast: Dict[str, Any], podcast_data: Dict[str, Any], 
                           episodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Update an existing podcast record and add new episodes.
    
    Args:
        db: Database manager
        existing_podcast: Existing podcast record
        podcast_data: New podcast data 
        episodes: List of episodes to add
        
    Returns:
        Dictionary with update results
    """
    # Podcast exists, update metadata if needed
    podcast_id = existing_podcast["id"]
    podcast_data["id"] = podcast_id
    needs_update = False
    
    # Check if any fields need updating
    for key, value in podcast_data.items():
        if key in existing_podcast and existing_podcast[key] != value:
            needs_update = True
            break
    
    if needs_update:
        db.upsert_podcast(podcast_data)
        logger.info(f"Updated podcast metadata for podcast ID: {podcast_id}")
    else:
        logger.info(f"No metadata changes for podcast ID: {podcast_id}")
    
    # Get existing episodes
    existing_episodes = db.list_episodes(podcast_id)
    # Track episodes by both audio_url and transcript_url for better identification
    existing_audio_urls = {ep["audio_url"] for ep in existing_episodes if ep["audio_url"]}
    existing_transcript_urls = {ep["transcript_url"] for ep in existing_episodes if ep.get("transcript_url")}
    
    # Add only new episodes
    new_episodes_count = 0
    # Calculate the starting episode number based on existing episodes
    next_episode_number = len(existing_episodes) + 1
    
    for episode in episodes:
        # Check if this episode already exists by audio_url or transcript_url
        audio_url = episode.get("audio_url", "")
        transcript_url = episode.get("transcript_url", "")
        if (audio_url and audio_url not in existing_audio_urls) or \
           (transcript_url and transcript_url not in existing_transcript_urls):
            episode["podcast_id"] = podcast_id
            episode["episode_number"] = next_episode_number  # Add episode number
            db.upsert_episode(episode)
            new_episodes_count += 1
            next_episode_number += 1
    
    logger.info(f"Added {new_episodes_count} new episodes to existing podcast ID: {podcast_id}")
    
    # Set podcast status to active after successful processing
    if new_episodes_count > 0 or needs_update:
        db.client.table("podcasts").update({
            "status": "active", 
            "updated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }).eq("id", podcast_id).execute()
        logger.info(f"Updated podcast status to active for podcast ID: {podcast_id}")
    
    return {
        "podcast_id": podcast_id,
        "title": podcast_data["title"],
        "new_episodes_added": new_episodes_count,
        "total_episodes": len(existing_episodes) + new_episodes_count,
        "status": "success"
    }

def create_new_podcast(db, podcast_data: Dict[str, Any], episodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Create a new podcast record with all its episodes.
    
    Args:
        db: Database manager
        podcast_data: Podcast data to insert
        episodes: List of episodes to add
        
    Returns:
        Dictionary with creation results
    """
    # Set the initial status to 'processing'
    podcast_data["status"] = "processing"
    podcast_id = db.upsert_podcast(podcast_data)
    
    # Insert all episodes
    episode_count = 0
    if episodes:
        for i, episode in enumerate(episodes, 1):
            episode["podcast_id"] = podcast_id
            episode["episode_number"] = i  # Set episode number starting from 1
            db.upsert_episode(episode)
            episode_count += 1
    
    logger.info(f"Successfully created new podcast with ID: {podcast_id} and {episode_count} episodes")
    
    # Update podcast status to 'active' now that all episodes are processed
    db.client.table("podcasts").update({
        "status": "active", 
        "updated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    }).eq("id", podcast_id).execute()
    logger.info(f"Updated podcast status to active for podcast ID: {podcast_id}")
    
    return {
        "podcast_id": podcast_id,
        "title": podcast_data["title"],
        "episode_count": episode_count,
        "status": "success"
    }
