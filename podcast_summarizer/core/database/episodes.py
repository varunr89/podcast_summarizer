"""
Episode database operations.
"""
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

class EpisodeManager:
    """
    Manager for episode-related database operations.
    """
    def __init__(self, client, logger):
        self.client = client
        self.logger = logger
    
    def upsert(self, episode_data: Dict[str, Any]) -> str:
        """
        Insert or update an episode record.
        
        Args:
            episode_data: Episode data to insert/update
            
        Returns:
            ID of the episode record
        """
        try:
            # Ensure we have an ID
            if "id" not in episode_data:
                episode_data["id"] = str(uuid.uuid4())
                
            # Add timestamps if not present
            current_time = datetime.now().isoformat()
            if "created_at" not in episode_data:
                episode_data["created_at"] = current_time
                
            episode_data["updated_at"] = current_time
            
            # Insert or update the episode record
            self.logger.debug(f"Upserting episode: {episode_data.get('title', 'Unknown')}")
            result = self.client.table("episodes").upsert(episode_data).execute()
            
            if result.data and len(result.data) > 0:
                episode_id = result.data[0].get("id")
                self.logger.debug(f"Episode upserted with ID: {episode_id}")
                return episode_id
            else:
                self.logger.error("Failed to upsert episode: no data returned")
                return episode_data["id"]
        except Exception as e:
            self.logger.error(f"Error upserting episode: {str(e)}")
            raise
    
    def list(self, podcast_id=None, limit=1000, offset=0) -> List[Dict[str, Any]]:
        """
        List episodes for a podcast, or all episodes if podcast_id is None.
        
        Args:
            podcast_id: ID of the podcast to list episodes for, or None for all episodes
            limit: Maximum number of episodes to return
            offset: Number of episodes to skip
            
        Returns:
            List of episode dictionaries
        """
        try:
            self.logger.debug(f"Listing episodes for podcast ID: {podcast_id if podcast_id else 'ALL'}, limit: {limit}, offset: {offset}")
            query = self.client.table("episodes").select("*")
            
            # Apply podcast_id filter only if provided
            if podcast_id is not None:
                query = query.eq("podcast_id", podcast_id)
                
            # Apply order, limit and offset
            result = query.order("published_at", desc=True).range(offset, offset + limit - 1).execute()
            
            self.logger.debug(f"Found {len(result.data) if result.data else 0} episodes")
            return result.data if result.data else []
        except Exception as e:
            self.logger.error(f"Error listing episodes: {str(e)}")
            return []
    
    def get(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details for a specific episode.
        
        Args:
            episode_id: ID of the episode to retrieve
            
        Returns:
            Episode dictionary or None if not found
        """
        try:
            self.logger.debug(f"Fetching episode with ID: {episode_id}")
            result = self.client.table("episodes").select("*").eq("id", episode_id).execute()
            
            if result.data and len(result.data) > 0:
                self.logger.debug(f"Found episode with ID: {episode_id}")
                return result.data[0]
            
            self.logger.warning(f"Episode not found with ID: {episode_id}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting episode details: {str(e)}")
            return None
