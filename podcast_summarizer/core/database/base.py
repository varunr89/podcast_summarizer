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
        self._email_preferences_manager = None
        self._user_follows_manager = None
        self._user_manager = None
    
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
    
    @property
    def email_preferences_manager(self):
        """Get an EmailPreferencesManager instance"""
        if self._email_preferences_manager is None:
            from .email_preferences import EmailPreferencesManager
            self._email_preferences_manager = EmailPreferencesManager(self.client, self.logger)
        return self._email_preferences_manager
    
    @property
    def user_follows_manager(self):
        """Get a UserFollowsManager instance"""
        if self._user_follows_manager is None:
            from .user_follows import UserFollowsManager
            self._user_follows_manager = UserFollowsManager(self.client, self.logger)
        return self._user_follows_manager
    
    @property
    def user_manager(self):
        """Get a UserManager instance"""
        if self._user_manager is None:
            from .users import UserManager
            self._user_manager = UserManager(self.client, self.logger)
        return self._user_manager
