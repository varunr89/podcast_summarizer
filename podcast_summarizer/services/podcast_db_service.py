"""
Service for podcast database operations.
"""
import time
from typing import Dict, List, Any, Optional

from ..core.logging_config import get_logger

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
    
    # Check if any fields need updating
    needs_update = any(existing_podcast.get(key) != value for key, value in podcast_data.items() if key in existing_podcast)
    
    if needs_update:
        db.podcast_manager.upsert(podcast_data)
        logger.info(f"Updated podcast metadata for podcast ID: {podcast_id}")
    else:
        logger.info(f"No metadata changes for podcast ID: {podcast_id}")
    
    # Get existing episodes
    existing_episodes = db.episode_manager.list(podcast_id=podcast_id, limit=1000)
    logger.debug(f"Found {len(existing_episodes)} existing episodes for podcast {podcast_id}")
    
    # Track episodes by both audio_url and transcript_url for better identification
    existing_audio_urls = {ep["audio_url"] for ep in existing_episodes if ep.get("audio_url")}
    existing_transcript_urls = {ep["transcript_url"] for ep in existing_episodes if ep.get("transcript_url")}
    
    # Add only new episodes
    new_episodes_count = 0
    next_episode_number = len(existing_episodes) + 1
    
    for episode in episodes:
        audio_url = episode.get("audio_url", "")
        transcript_url = episode.get("transcript_url", "")
        
        # Skip episodes that already exist
        if (audio_url and audio_url in existing_audio_urls) or \
           (transcript_url and transcript_url in existing_transcript_urls):
            continue
            
        episode["podcast_id"] = podcast_id
        episode["episode_number"] = next_episode_number
        db.episode_manager.upsert(episode)
        new_episodes_count += 1
        next_episode_number += 1
    
    logger.info(f"Added {new_episodes_count} new episodes to existing podcast ID: {podcast_id}")
    
    # Update podcast status if changes were made
    if new_episodes_count > 0 or needs_update:
        db.client.table("podcasts").update({
            "status": "active", 
            "updated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }).eq("id", podcast_id).execute()
    
    return {
        "podcast_id": podcast_id,
        "title": podcast_data["title"],
        "new_episodes_added": new_episodes_count,
        "total_episodes": len(existing_episodes) + new_episodes_count,
        "status": "success"
    }

def create_new_podcast(db, podcast_data, episodes_data):
    """
    Create a new podcast and add its episodes.
    """
    # Set status to pending initially
    podcast_data["status"] = "pending"
    
    # Use podcast_manager instead of direct calls
    podcast_id = db.podcast_manager.upsert(podcast_data)
    
    # Add episodes using episode_manager
    episodes_added = 0
    try:
        for episode in episodes_data:
            # Set the podcast ID for each episode
            episode["podcast_id"] = podcast_id
            
            # Use episode_manager instead of direct calls
            db.episode_manager.upsert(episode)
            episodes_added += 1
        
        # After all episodes are added successfully, update status to active
        db.client.table("podcasts").update({
            "status": "active", 
            "updated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }).eq("id", podcast_id).execute()
        
        logger.info(f"Podcast ID {podcast_id} status set to active after adding {episodes_added} episodes")
        
        return {
            "podcast_id": podcast_id,
            "episodes_added": episodes_added,
            "status": "active"
        }
    except Exception as e:
        logger.error(f"Error adding episodes to podcast {podcast_id}: {str(e)}")
        # In case of failure, leave status as pending
        raise

def update_existing_podcast(db, existing_podcast, podcast_data, episodes_data):
    """
    Update an existing podcast and add any new episodes.
    """
    # Include the ID in podcast data
    podcast_id = existing_podcast["id"]
    podcast_data["id"] = podcast_id
    
    # Use podcast_manager instead of direct calls
    db.podcast_manager.upsert(podcast_data)
    
    # Get existing episodes for this podcast
    existing_episodes = db.episode_manager.list(podcast_id=podcast_id)
    
    # Create a set of existing GUIDs for quick lookup
    existing_guids = {episode.get("guid") for episode in existing_episodes if episode.get("guid")}
    
    # Check existing episodes and add new ones
    episodes_added = 0
    try:
        for episode in episodes_data:
            # Set the podcast ID for each episode
            episode["podcast_id"] = podcast_id
            
            # Check if episode exists by GUID
            if episode.get("guid") not in existing_guids:
                # Use episode_manager to add new episode
                db.episode_manager.upsert(episode)
                episodes_added += 1
        
        # After all episodes are added successfully, update status to active
        db.client.table("podcasts").update({
            "status": "active", 
            "updated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }).eq("id", podcast_id).execute()
        
        logger.info(f"Podcast ID {podcast_id} status set to active after adding {episodes_added} episodes")
        
        return {
            "podcast_id": podcast_id,
            "new_episodes_added": episodes_added,
            "total_episodes": len(existing_episodes) + episodes_added,
            "status": "active"
        }
    except Exception as e:
        logger.error(f"Error adding episodes to existing podcast {podcast_id}: {str(e)}")
        raise

def get_episode(db, episode_id: str) -> Optional[Dict[str, Any]]:
    """
    Get episode details by ID without full transcript.
    """
    try:
        result = db.client.table("episodes").select("*").eq("id", episode_id).limit(1).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Error fetching episode from database: {str(e)}")
        raise

def list_all_episodes(db, limit: int = 100, offset: int = 0, order_by: str = "published_at") -> List[Dict[str, Any]]:
    """
    List all episodes across all podcasts with flexible ordering.
    """
    try:
        result = db.client.table("episodes")\
                  .select("*")\
                  .order(order_by, desc=True)\
                  .range(offset, offset + limit - 1)\
                  .execute()
        
        return result.data
    except Exception as e:
        logger.error(f"Error listing episodes from database: {str(e)}")
        raise
