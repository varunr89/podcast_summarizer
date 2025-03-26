from typing import Dict, Any, List, Optional

class UserFollowsManager:
    """Manager for user podcast follows table operations."""
    
    def __init__(self, client, logger):
        self.client = client
        self.logger = logger
        self.table = "user_follows"
    
    def list_followed_podcasts(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all podcasts followed by a user.
        
        Args:
            user_id: The user's ID
            
        Returns:
            List of dictionaries containing podcast details
        """
        try:
            response = self.client.from_(self.table)\
                .select("podcast_id, created_at")\
                .eq("user_id", user_id)\
                .order("created_at", desc=True)\
                .execute()
                
            return response.data if response.data else []
            
        except Exception as e:
            self.logger.error(f"Error fetching followed podcasts for user {user_id}: {str(e)}")
            return []
    
    def follow_podcast(self, user_id: str, podcast_id: str) -> bool:
        """
        Add a podcast follow for a user.
        
        Args:
            user_id: The user's ID
            podcast_id: The podcast's ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            data = {
                "user_id": user_id,
                "podcast_id": podcast_id
            }
            
            response = self.client.from_(self.table)\
                .upsert(data)\
                .execute()
                
            return bool(response.data)
            
        except Exception as e:
            self.logger.error(f"Error following podcast {podcast_id} for user {user_id}: {str(e)}")
            return False
    
    def unfollow_podcast(self, user_id: str, podcast_id: str) -> bool:
        """
        Remove a podcast follow for a user.
        
        Args:
            user_id: The user's ID
            podcast_id: The podcast's ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            response = self.client.from_(self.table)\
                .delete()\
                .eq("user_id", user_id)\
                .eq("podcast_id", podcast_id)\
                .execute()
                
            return bool(response.data)
            
        except Exception as e:
            self.logger.error(f"Error unfollowing podcast {podcast_id} for user {user_id}: {str(e)}")
            return False