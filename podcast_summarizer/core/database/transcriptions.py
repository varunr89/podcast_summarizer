"""
Transcription database operations.
"""
from datetime import datetime
from typing import Dict, Any, Optional

class TranscriptionManager:
    """
    Manager for transcription-related database operations.
    """
    def __init__(self, client, logger):
        self.client = client
        self.logger = logger
    
    def get(self, episode_id: str) -> Optional[str]:
        """
        Get the transcription for a specific episode.
        
        Args:
            episode_id: ID of the episode
            
        Returns:
            Transcription text or None if not found
        """
        try:
            self.logger.debug(f"Fetching transcription for episode ID: {episode_id}")
            # Direct query to get only the transcript field
            result = self.client.table("episodes").select("transcript").eq("id", episode_id).execute()
            
            if result.data and len(result.data) > 0 and "transcript" in result.data[0]:
                transcript = result.data[0]["transcript"]
                if transcript:
                    self.logger.debug(f"Found transcript of length: {len(transcript)} characters")
                    return transcript
                else:
                    self.logger.warning(f"Transcript is empty for episode ID: {episode_id}")
            else:
                self.logger.warning(f"No transcript found for episode ID: {episode_id}")
            
            return None
        except Exception as e:
            self.logger.error(f"Error fetching transcript: {str(e)}")
            return None
    
    def get_episode_with_transcript(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details for a specific episode with transcript.
        
        Args:
            episode_id: ID of the episode to retrieve
            
        Returns:
            Episode dictionary with transcript or None if not found
        """
        try:
            self.logger.debug(f"Fetching episode with transcript for ID: {episode_id}")
            from .episodes import EpisodeManager
            episode_manager = EpisodeManager(self.client, self.logger)
            
            # First get the basic episode data
            episode = episode_manager.get(episode_id)
            
            if not episode:
                return None
            
            # Then get the transcript
            transcript = self.get(episode_id)
            
            if transcript:
                episode["transcript"] = transcript
            
            return episode
        except Exception as e:
            self.logger.error(f"Error getting episode with transcript: {str(e)}")
            return None
    
    def store(self, episode_data: Dict[str, Any], transcription: str) -> None:
        """
        Store a transcription for an episode.
        
        Args:
            episode_data: Episode data dictionary
            transcription: Transcription text
        """
        try:
            self.logger.debug(f"Storing transcription for episode ID: {episode_data.get('id')}")
            
            # Update the episode with the transcription
            update_data = {
                "id": episode_data.get("id"),
                "podcast_id": episode_data.get("podcast_id"),
                "transcript": transcription,
                "transcript_url": episode_data.get("transcript_url"),
                "updated_at": datetime.now().isoformat(),
                "transcription_status": "completed"
            }
            
            result = self.client.table("episodes").update(update_data).eq("id", episode_data.get("id")).execute()
            
            if not result.data or len(result.data) == 0:
                self.logger.error(f"Failed to update episode with transcription")
            else:
                self.logger.info(f"Transcription stored successfully for episode ID: {episode_data.get('id')}")
        except Exception as e:
            self.logger.error(f"Error storing transcription: {str(e)}")
            raise
