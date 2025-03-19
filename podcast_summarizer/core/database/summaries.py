"""
Summary database operations.
"""
import uuid
import json
from datetime import datetime
from typing import Dict, Any, List

class SummaryManager:
    """
    Manager for summary-related database operations.
    """
    def __init__(self, client, logger):
        self.client = client
        self.logger = logger
    
    def store(
        self, 
        episode_id: str, 
        summary: str, 
        user_id: str = None,
        key_points: Dict[str, Any] = None,
        highlights: List[str] = None,
        detail_level: str = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Store a summary for an episode.
        
        Args:
            episode_id: ID of the episode
            summary: Summary text
            user_id: Optional user ID
            key_points: Optional key points dictionary
            highlights: Optional highlights list
            detail_level: Optional detail level
            metadata: Optional metadata dictionary
            
        Returns:
            ID of the stored summary
        """
        try:
            self.logger.debug(f"Storing summary for episode ID: {episode_id}")
            
            # Create summary record directly - no need to fetch episode first
            summary_id = str(uuid.uuid4())
            summary_data = {
                "id": summary_id,
                "episode_id": episode_id,
                "summary": summary,
                "user_id": user_id,
                "key_points": json.dumps(key_points) if key_points else None,
                "highlights": json.dumps(highlights) if highlights else None,
                "detail_level": detail_level,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "metadata": json.dumps(metadata) if metadata else None
            }
            
            result = self.client.table("episode_summaries").insert(summary_data).execute()
            self.logger.info(f"Summary stored with ID: {summary_id}")
            
            return summary_id
        except Exception as e:
            self.logger.error(f"Error storing summary: {str(e)}")
            raise
