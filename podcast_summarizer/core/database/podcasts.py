"""
Podcast database operations.
"""
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

class PodcastManager:
    """
    Manager for podcast-related database operations.
    """
    def __init__(self, client, logger):
        self.client = client
        self.logger = logger
    
    def get_by_feed_url(self, feed_url: str) -> Optional[Dict[str, Any]]:
        """
        Get a podcast by its feed URL.
        
        Args:
            feed_url: URL of the podcast feed
            
        Returns:
            Podcast dictionary or None if not found
        """
        try:
            result = self.client.table("podcasts").select("*").eq("feed_url", feed_url).execute()
            
            if result.data and len(result.data) > 0:
                self.logger.debug(f"Found podcast with feed URL: {feed_url}")
                return result.data[0]
                
            self.logger.debug(f"No podcast found with feed URL: {feed_url}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting podcast by feed URL: {str(e)}")
            return None
    
    def upsert(self, podcast_data: Dict[str, Any]) -> str:
        """
        Insert or update a podcast record.
        
        Args:
            podcast_data: Podcast data to insert/update
            
        Returns:
            ID of the podcast record
        """
        try:
            # Ensure we have an ID
            if "id" not in podcast_data:
                podcast_data["id"] = str(uuid.uuid4())
                
            # Add timestamps if not present
            current_time = datetime.now().isoformat()
            if "created_at" not in podcast_data:
                podcast_data["created_at"] = current_time
                
            podcast_data["updated_at"] = current_time
            
            # Insert or update the podcast record
            self.logger.debug(f"Upserting podcast: {podcast_data.get('title', 'Unknown')}")
            result = self.client.table("podcasts").upsert(podcast_data).execute()
            
            if result.data and len(result.data) > 0:
                podcast_id = result.data[0].get("id")
                self.logger.debug(f"Podcast upserted with ID: {podcast_id}")
                return podcast_id
            else:
                self.logger.error("Failed to upsert podcast: no data returned")
                return podcast_data["id"]
        except Exception as e:
            self.logger.error(f"Error upserting podcast: {str(e)}")
            raise
