"""
Base database client functionality.
"""
import os
from supabase import create_client
from ...core.logging_config import get_logger

# Global database client
_db_instance = None

def get_db():
    """
    Get a singleton instance of the database client.
    """
    global _db_instance
    if (_db_instance is None):
        _db_instance = SupabaseManager()
    return _db_instance

class SupabaseManager:
    """
    Base interface for Supabase operations.
    """
    def __init__(self):
        self.logger = get_logger(__name__)
        
        # Get credentials from environment variables
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        
        if not self.url or not self.key:
            self.logger.error("Supabase credentials missing from environment variables")
            raise ValueError("Supabase URL and key must be provided as environment variables")
            
        self.logger.info(f"Initializing Supabase client with URL: {self.url}")
        self.client = create_client(self.url, self.key)
        self.logger.info(f"Supabase client initialized successfully")
        
        # Initialize instance variables for managers
        self._podcast_manager = None
        self._episode_manager = None
        self._transcription_manager = None
        self._summary_manager = None
    
    @property
    def podcast_manager(self):
        """Get a PodcastManager instance"""
        if self._podcast_manager is None:
            from .podcasts import PodcastManager
            self._podcast_manager = PodcastManager(self.client, self.logger)
        return self._podcast_manager
    
    @property
    def episode_manager(self):
        """Get an EpisodeManager instance"""
        if self._episode_manager is None:
            from .episodes import EpisodeManager
            self._episode_manager = EpisodeManager(self.client, self.logger)
        return self._episode_manager
    
    @property
    def transcription_manager(self):
        """Get a TranscriptionManager instance"""
        if self._transcription_manager is None:
            from .transcriptions import TranscriptionManager
            self._transcription_manager = TranscriptionManager(self.client, self.logger)
        return self._transcription_manager
    
    @property
    def summary_manager(self):
        """Get a SummaryManager instance"""
        if self._summary_manager is None:
            from .summaries import SummaryManager
            self._summary_manager = SummaryManager(self.client, self.logger)
        return self._summary_manager
