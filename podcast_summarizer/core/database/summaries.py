from typing import Dict, Any, Optional, List, Tuple

class SummaryManager:
    """Manager for episode summaries and email tracking."""
    
    def __init__(self, client, logger):
        self.client = client
        self.logger = logger
        self.table = "episode_summaries"
        self.logger.info("Initialized SummaryManager")
    
    def get(self, episode_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get summary for an episode, optionally for a specific user.
        
        Args:
            episode_id: The episode's ID
            user_id: Optional user ID to check email status
            
        Returns:
            Dict containing summary or None if not found
        """
        self.logger.debug(f"Fetching summary for episode: {episode_id}, user: {user_id}")
        try:
            query = self.client.from_(self.table)\
                .select("*")\
                .eq("episode_id", episode_id)
                
            if user_id:
                query = query.eq("user_id", user_id)
                
            response = query.single().execute()
                
            if response.data:
                self.logger.info(f"Found summary for episode {episode_id}")
                return response.data
            
            self.logger.info(f"No summary found for episode {episode_id}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error fetching summary for episode {episode_id}: {str(e)}")
            return None
    
    def get_unemailed_summaries(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get summaries that haven't been emailed for a given user.
        
        Args:
            user_id: The user's ID
            limit: Maximum number of summaries to return
            
        Returns:
            List of summaries that haven't been emailed
        """
        self.logger.debug(f"Fetching unemailed summaries for user {user_id}")
        try:
            response = self.client.from_(self.table)\
                .select("*")\
                .eq("user_id", user_id)\
                .eq("summary_emailed", False)\
                .limit(limit)\
                .execute()
                
            if response.data:
                self.logger.info(f"Found {len(response.data)} unemailed summaries")
                return response.data
            
            self.logger.info("No unemailed summaries found")
            return []
            
        except Exception as e:
            self.logger.error(f"Error fetching unemailed summaries: {str(e)}")
            return []
    
    def store(self, episode_id: str, summary: str, user_id: str, 
             key_points: List[str], highlights: List[str], 
             detail_level: str, metadata: Dict[str, Any]) -> str:
        """
        Store a summary for an episode.
        
        Args:
            episode_id: The episode's ID
            summary: The generated summary
            user_id: ID of the user who requested the summary
            key_points: List of key points
            highlights: List of highlights
            detail_level: Summary detail level
            metadata: Additional metadata
            
        Returns:
            str: ID of the stored summary
        """
        self.logger.debug(f"Storing summary for episode {episode_id}, user {user_id}")
        try:
            data = {
                "episode_id": episode_id,
                "summary": summary,
                "user_id": user_id,
                "key_points": key_points,
                "highlights": highlights,
                "detail_level": detail_level,
                "metadata": metadata,
                "summary_emailed": False  # Initialize as not emailed
            }
            
            self.logger.debug(f"Summary length: {len(summary)} chars")
            self.logger.debug(f"Key points: {len(key_points)}, Highlights: {len(highlights)}")
            
            response = self.client.from_(self.table)\
                .upsert(data)\
                .execute()
                
            if response.data:
                summary_id = response.data[0].get('id')
                self.logger.info(f"Successfully stored summary with ID: {summary_id}")
                return summary_id
                
            raise ValueError("Failed to store summary")
            
        except Exception as e:
            self.logger.error(f"Error storing summary for episode {episode_id}: {str(e)}")
            raise
    
    def mark_as_emailed(self, episode_ids: List[str], user_id: str) -> bool:
        """
        Mark summaries as emailed for the given episodes and user.
        
        Args:
            episode_ids: List of episode IDs to mark
            user_id: The user who received the email
            
        Returns:
            bool: True if successful, False otherwise
        """
        self.logger.debug(f"Marking {len(episode_ids)} summaries as emailed for user {user_id}")
        try:
            response = self.client.from_(self.table)\
                .update({"summary_emailed": True})\
                .in_("episode_id", episode_ids)\
                .eq("user_id", user_id)\
                .execute()
                
            if response.data:
                self.logger.info(f"Successfully marked {len(episode_ids)} summaries as emailed")
                return True
                
            self.logger.warning("No summaries were updated")
            return False
            
        except Exception as e:
            self.logger.error(f"Error marking summaries as emailed: {str(e)}")
            return False
