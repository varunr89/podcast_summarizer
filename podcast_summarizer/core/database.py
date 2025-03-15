"""
Database integration with Supabase.
"""
import time
import uuid
from typing import Dict, Any, Optional
import feedparser

from supabase import create_client

from .logging_config import get_logger
from .config import get_settings

logger = get_logger(__name__)

class SupabaseManager:
    """Manages interactions with Supabase database."""
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern to ensure only one client instance."""
        if cls._instance is None:
            cls._instance = super(SupabaseManager, cls).__new__(cls)
            cls._instance._initialize_client()
        return cls._instance
    
    def _initialize_client(self):
        """Initialize the Supabase client."""
        settings = get_settings()
        try:
            # Validate Supabase URL and key before creating client
            supabase_url = str(settings.SUPABASE_URL)
            supabase_key = str(settings.SUPABASE_KEY)
            
            if not supabase_url or not supabase_key:
                logger.error("Supabase URL or key is empty")
                raise ValueError("Supabase URL and key must be provided")
                
            logger.info(f"Initializing Supabase client with URL: {supabase_url}")
            self.client = create_client(supabase_url, supabase_key)
            logger.info("Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {str(e)}")
            self.client = None
            raise
    
    def store_podcast_feed(self, feed_url: str) -> str:
        """
        Parse a podcast RSS feed and store the information in Supabase.
        
        Args:
            feed_url: URL of the podcast RSS feed
            
        Returns:
            ID of the stored record
            
        Raises:
            RuntimeError: If the client is not initialized, RSS parsing fails, or storage fails
        """
        if not self.client:
            logger.error("Supabase client not initialized")
            raise RuntimeError("Supabase client not initialized")
        
        try:
            # Parse the RSS feed
            logger.debug(f"Parsing podcast feed from {feed_url}")
            feed = feedparser.parse(feed_url)
            
            if not feed or not feed.get('feed'):
                logger.error(f"Failed to parse podcast feed from {feed_url}")
                raise RuntimeError(f"Failed to parse podcast feed from {feed_url}")
            
            # Extract podcast information
            feed_data = feed.get('feed', {})
            title = feed_data.get('title', 'Unknown Podcast')
            description = feed_data.get('description', feed_data.get('subtitle', ''))
            author = feed_data.get('author', feed_data.get('itunes_author', ''))
            
            # Look for artwork in itunes_image or regular image
            artwork_url = ''
            if 'image' in feed_data and 'href' in feed_data['image']:
                artwork_url = feed_data['image']['href']
            elif 'itunes_image' in feed_data and 'href' in feed_data['itunes_image']:
                artwork_url = feed_data['itunes_image']['href']
                
            # Prepare data for insertion
            record_id = str(uuid.uuid4())
            record = {
                "id": record_id,
                "feed_url": feed_url,
                "title": title,
                "description": description,
                "artwork_url": artwork_url,
                "author": author,
                "language": feed_data.get('language', ''),
                "status": 'active',
                "created_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                "updated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }
            
            logger.debug(f"Storing podcast feed for {title}")
            
            # Insert into podcast_feeds table
            result = self.client.table("podcasts").insert(record).execute()
            
            if result.data:
                logger.info(f"Stored podcast feed for {title} with ID {record_id}")
                return record_id
            else:
                logger.error(f"Failed to store podcast feed: {result.error}")
                raise RuntimeError(f"Failed to store podcast feed: {result.error}")
        
        except Exception as e:
            logger.error(f"Error processing or storing podcast feed: {str(e)}")
            raise

    def store_transcription(self, episode_data: Dict[str, Any], transcription: str) -> str:
        """
        Store a podcast episode transcription in Supabase by updating an existing episode.
        
        Args:
            episode_data: Metadata about the podcast episode
            transcription: The transcribed text
            
        Returns:
            ID of the updated record
            
        Raises:
            RuntimeError: If the client is not initialized or storage fails
            ValueError: If podcast_id is missing or invalid or if the episode doesn't exist
        """
        if not self.client:
            logger.error("Supabase client not initialized")
            raise RuntimeError("Supabase client not initialized")
        
        # Validate episode_id exists
        episode_id = episode_data.get("id")
        if not episode_id:
            logger.error("Missing episode id in episode_data")
            raise ValueError("episode_id is required in episode_data")
            
        # Validate podcast_id exists and is valid
        podcast_id = episode_data.get("podcast_id")
        if not podcast_id:
            logger.error("Missing podcast_id in episode data")
            raise ValueError("podcast_id is required in episode_data")
        
        # Verify the podcast exists in the database
        podcast = self.get_podcast(podcast_id)
        if not podcast:
            logger.error(f"Referenced podcast with ID {podcast_id} does not exist")
            raise ValueError(f"Referenced podcast with ID {podcast_id} does not exist")
        
        # Verify the episode exists in the database
        existing_episode = self.get_episode(episode_id)
        if not existing_episode:
            logger.error(f"Episode with ID {episode_id} does not exist - cannot store transcription")
            raise ValueError(f"Episode with ID {episode_id} does not exist - cannot store transcription")
        
        try:
            # Ensure we have a published_at date (use current time if not provided)
            published_at = episode_data.get("published_date") or episode_data.get("published_at") or existing_episode.get("published_at")
            if not published_at:
                published_at = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                logger.warning(f"No published date found for episode, using current time: {published_at}")
                
            # Prepare data for update
            update_data = {
                "title": episode_data.get("title") or existing_episode.get("title", "Unknown Episode"),
                "description": episode_data.get("description") or existing_episode.get("description", ""),
                "published_at": published_at,
                "audio_url": episode_data.get("audio_url") or existing_episode.get("audio_url", ""),  # Add back audio_url
                "transcript_url": episode_data.get("transcript_url") or existing_episode.get("transcript_url", ""),
                "transcript": transcription,
                "updated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }
            
            if "episode_number" in episode_data:
                update_data["episode_number"] = episode_data["episode_number"]
            
            logger.debug(f"Updating transcription for episode {episode_id} in podcast {podcast_id}")
            
            # Update the existing episode
            result = self.client.table("episodes").update(update_data).eq("id", episode_id).execute()
            
            if result.data:
                logger.info(f"Updated transcription for episode {episode_id} with title '{update_data['title']}'")
                return episode_id
            else:
                logger.error(f"Failed to update transcription: {result.error}")
                raise RuntimeError(f"Failed to update transcription: {result.error}")
        
        except Exception as e:
            logger.error(f"Error updating transcription in Supabase: {str(e)}")
            raise
    
    def store_summary(self, episode_id: str, summary: str, user_id: str, key_points: Dict[str, Any], highlights: list, detail_level: str) -> str:
        """
        Store a podcast episode summary in Supabase.
        
        Args:
            episode_id: ID of the episode record
            summary: Generated summary text
            user_id: ID of the user
            key_points: Key points of the summary
            highlights: Highlights of the summary
            detail_level: Detail level of the summary
            
        Returns:
            ID of the stored summary record
            
        Raises:
            RuntimeError: If the client is not initialized or storage fails
            ValueError: If the episode_id is invalid
        """
        if not self.client:
            logger.error("Supabase client not initialized")
            raise RuntimeError("Supabase client not initialized")
        
        # Verify the episode exists in the database
        episode = self.get_episode(episode_id)
        if not episode:
            logger.error(f"Referenced episode with ID {episode_id} does not exist")
            raise ValueError(f"Referenced episode with ID {episode_id} does not exist")
        
        try:
            # Prepare data for insertion
            record_id = str(uuid.uuid4())
            record = {
                "id": record_id,
                "episode_id": episode_id,
                "user_id": user_id,
                "summary": summary,
                "key_points": key_points,
                "highlights": highlights,
                "detail_level": detail_level,
                "created_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                "updated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }
            
            logger.debug(f"Storing summary for episode {episode_id}")
            
            # Insert into episode_summaries table
            result = self.client.table("episode_summaries").insert(record).execute()
            
            if result.data:
                logger.info(f"Stored summary for episode {episode_id} with ID {record_id}")
                return record_id
            else:
                logger.error(f"Failed to store summary: {result.error}")
                raise RuntimeError(f"Failed to store summary: {result.error}")
        
        except Exception as e:
            logger.error(f"Error storing summary in Supabase: {str(e)}")
            raise
    
    def get_transcription(self, episode_id: str) -> Optional[str]:
        """
        Retrieve a transcription from Supabase by episode ID.
        
        Args:
            episode_id: ID of the episode record
            
        Returns:
            Transcription text if found, None otherwise
        """
        if not self.client:
            logger.error("Supabase client not initialized")
            raise RuntimeError("Supabase client not initialized")
        
        try:
            result = self.client.table("podcast_transcriptions") \
                                .select("transcription") \
                                .eq("id", episode_id).execute()
            
            if result.data:
                return result.data[0].get("transcription")
            else:
                logger.warning(f"Transcription not found for episode {episode_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving transcription: {str(e)}")
            raise

    def get_podcast(self, podcast_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve podcast information from Supabase by podcast ID.
        
        Args:
            podcast_id: ID of the podcast record
            
        Returns:
            Podcast data if found, None otherwise
        """
        if not self.client:
            logger.error("Supabase client not initialized")
            raise RuntimeError("Supabase client not initialized")
        
        try:
            result = self.client.table("podcasts") \
                                .select("*") \
                                .eq("id", podcast_id).execute()
            
            if result.data:
                return result.data[0]
            else:
                logger.warning(f"Podcast not found with ID {podcast_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving podcast: {str(e)}")
            raise
    
    def get_podcast_by_feed_url(self, feed_url: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve podcast information from Supabase by feed URL.
        
        Args:
            feed_url: URL of the podcast RSS feed
            
        Returns:
            Podcast data if found, None otherwise
        """
        if not self.client:
            logger.error("Supabase client not initialized")
            raise RuntimeError("Supabase client not initialized")
        
        try:
            result = self.client.table("podcasts") \
                                .select("*") \
                                .eq("feed_url", feed_url).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            else:
                logger.debug(f"Podcast not found with feed URL {feed_url}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving podcast by feed URL: {str(e)}")
            raise

    def list_episodes(self, podcast_id: str) -> list:
        """
        List all episodes for a specific podcast.
        
        Args:
            podcast_id: ID of the podcast
            
        Returns:
            List of episode records
        """
        if not self.client:
            logger.error("Supabase client not initialized")
            raise RuntimeError("Supabase client not initialized")
        
        try:
            # Include both audio_url and transcript_url in the selected fields
            result = self.client.table("episodes") \
                                .select("id,title,description,published_at,audio_url,transcript_url") \
                                .eq("podcast_id", podcast_id) \
                                .order("published_at", desc=True) \
                                .execute()
            
            return result.data
                
        except Exception as e:
            logger.error(f"Error listing episodes: {str(e)}")
            raise

    def get_episode(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve episode information without transcript.
        
        Args:
            episode_id: ID of the episode record
            
        Returns:
            Episode data if found, None otherwise
        """
        if not self.client:
            logger.error("Supabase client not initialized")
            raise RuntimeError("Supabase client not initialized")
        
        try:
            # Include both audio_url and transcript_url in the selected fields
            result = self.client.table("episodes") \
                                .select("id,podcast_id,title,description,published_at,audio_url,transcript_url") \
                                .eq("id", episode_id).execute()
            
            if result.data:
                return result.data[0]
            else:
                logger.warning(f"Episode not found with ID {episode_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving episode: {str(e)}")
            raise

    def get_user_summaries(self, user_id: str, episode_id: Optional[str] = None) -> list:
        """
        Get summaries created by a specific user, optionally filtered by episode.
        
        Args:
            user_id: ID of the user
            episode_id: Optional ID of the episode
            
        Returns:
            List of summary records
        """
        if not self.client:
            logger.error("Supabase client not initialized")
            raise RuntimeError("Supabase client not initialized")
        
        try:
            query = self.client.table("episode_summaries") \
                              .select("*") \
                              .eq("user_id", user_id)
                              
            if episode_id:
                query = query.eq("episode_id", episode_id)
                
            result = query.order("created_at", desc=True).execute()
            
            return result.data
                
        except Exception as e:
            logger.error(f"Error retrieving user summaries: {str(e)}")
            raise

    def get_summary(self, summary_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific summary by ID.
        
        Args:
            summary_id: ID of the summary record
            
        Returns:
            Summary data if found, None otherwise
        """
        if not self.client:
            logger.error("Supabase client not initialized")
            raise RuntimeError("Supabase client not initialized")
        
        try:
            result = self.client.table("episode_summaries") \
                                .select("*") \
                                .eq("id", summary_id).execute()
            
            if result.data:
                return result.data[0]
            else:
                logger.warning(f"Summary not found with ID {summary_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving summary: {str(e)}")
            raise

    def get_episode_with_transcript(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve complete episode information including transcript.
        
        Args:
            episode_id: ID of the episode record
            
        Returns:
            Episode data with transcript if found, None otherwise
        """
        if not self.client:
            logger.error("Supabase client not initialized")
            raise RuntimeError("Supabase client not initialized")
        
        try:
            result = self.client.table("episodes") \
                                .select("*") \
                                .eq("id", episode_id).execute()
            
            if result.data:
                return result.data[0]
            else:
                logger.warning(f"Episode not found with ID {episode_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving episode with transcript: {str(e)}")
            raise

    def upsert_podcast(self, podcast_data: dict) -> str:
        """
        Insert or update a podcast in the Supabase podcasts table.
        Returns the podcast ID.
        """
        # Check if podcast already exists based on feed_url
        existing = self.get_podcast_by_feed_url(podcast_data["feed_url"])
        
        if existing:
            # Update existing podcast
            podcast_id = existing["id"]
            self.client.table("podcasts").update(podcast_data).eq("id", podcast_id).execute()
        else:
            # Insert new podcast
            result = self.client.table("podcasts").insert(podcast_data).execute()
            podcast_id = result.data[0]["id"]
        
        return podcast_id

    def upsert_episode(self, episode_data: dict) -> str:
        """
        Insert or update an episode in the Supabase episodes table.
        Returns the episode ID.
        """
        try:
            podcast_id = episode_data["podcast_id"]
            
            # Find by podcast_id and title - this is the most reliable way to identify an episode
            if "title" in episode_data and episode_data["title"]:
                existing = self.client.table("episodes").select("id").eq("podcast_id", podcast_id).eq("title", episode_data["title"]).execute()
                if existing.data and len(existing.data) > 0:
                    # Update existing episode
                    episode_id = existing.data[0]["id"]
                    self.client.table("episodes").update(episode_data).eq("id", episode_id).execute()
                    logger.info(f"Updated existing episode with ID {episode_id} (podcast: {podcast_id}, title: {episode_data['title']})")
                    return episode_id
            
            # If no existing episode found, insert new one
            result = self.client.table("episodes").insert(episode_data).execute()
            episode_id = result.data[0]["id"]
            logger.info(f"Inserted new episode with ID {episode_id} (podcast: {podcast_id}, title: {episode_data['title']})")
            return episode_id
            
        except Exception as e:
            logger.error(f"Error in upsert_episode: {str(e)}")
            raise

def get_db():
    """Get database manager instance."""
    return SupabaseManager()
