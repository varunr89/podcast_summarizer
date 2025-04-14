"""
Functions for handling podcast transcripts.
"""
import time
import json
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

from ...core.logging_config import get_logger

logger = get_logger(__name__)

def get_existing_transcript(episode, db):
    """Get existing transcript from the database if available."""
    if "id" in episode:
        try:
            existing_episode = db.episode_manager.get(episode["id"])
            logger.info(f"Checking if transcript exists for episode {episode['id']}")
            if existing_episode and "transcript" in existing_episode and existing_episode["transcript"]:
                logger.info(f"Found existing transcript for episode {episode['id']}")
                return existing_episode["transcript"]
        except Exception as e:
            logger.warning(f"Error checking for existing transcript: {str(e)}")
    return None

def save_transcription(episode, podcast_id, transcription, transcript_blob_name,
                      audio_blob_name, storage, db, keep_audio_files, error_message=None):
    """Save transcription to storage and database, or log error if processing failed."""
    # Ensure episode has podcast_id
    if "podcast_id" not in episode or not episode["podcast_id"]:
        episode["podcast_id"] = podcast_id
    
    # Ensure episode has an ID
    episode_id = episode.get("id")
    if not episode_id:
        logger.error("Cannot save transcription or error status without episode ID.")
        return

    # Ensure published_date exists for consistency, even on failure
    if "published_date" not in episode:
        episode["published_date"] = episode.get("published_at", time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))

    if error_message:
        # Handle error case: update status and log error message
        logger.error(f"Processing failed for episode {episode_id}: {error_message}")
        try:
            # Use direct execute for simplicity in updating status and error
            update_data = {
                "transcription_status": "failed",
                "processing_error": error_message,
                "updated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }
            result = db.client.table("episodes").update(update_data).eq("id", episode_id).execute()
            if not result.data or len(result.data) == 0:
                logger.error(f"Failed to update episode {episode_id} status to failed in DB.")
            else:
                logger.info(f"Updated episode {episode_id} status to failed in DB.")
        except Exception as e:
            logger.error(f"Error updating episode {episode_id} status in DB: {str(e)}")
    else:
        # Handle success case: upload transcript and update DB
        try:
            # Upload transcript
            transcript_url = storage.upload_text(transcription, transcript_blob_name)
            episode["transcript_url"] = transcript_url
            
            # Set transcription status to completed
            episode["transcription_status"] = "completed"
            episode["processing_error"] = None # Clear any previous error
            
            # Store in database using the manager
            db.transcription_manager.store(episode, transcription)
            logger.info(f"Transcription completed and stored for episode: {episode['title']}")
            
            # Delete audio blob after successful transcription (unless keep_audio_files is true)
            if not keep_audio_files:
                try:
                    storage.delete_blob(audio_blob_name)
                    logger.info(f"Deleted audio file from storage: {audio_blob_name}")
                except Exception as e:
                    logger.warning(f"Failed to delete audio file from storage: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to store transcription for episode {episode_id}: {str(e)}")
            # Attempt to mark as failed if storing success fails
            try:
                error_msg = f"Failed during final storage: {str(e)}"
                update_data = {
                    "transcription_status": "failed",
                    "processing_error": error_msg,
                    "updated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                }
                db.client.table("episodes").update(update_data).eq("id", episode_id).execute()
            except Exception as final_err:
                logger.error(f"Critical error: Failed to mark episode {episode_id} as failed after storage error: {final_err}")

async def fetch_publisher_transcript(publisher_transcript_url: str) -> str:
    """Extract text content from transcript URL"""
    # Define schema for paragraph text extraction
    schema = {
        "name": "Transcript Text Extractor",
        "baseSelector": "body",
        "fields": [
            {
                "name": "paragraph_content",
                "selector": "p",
                "type": "text"
            }
        ]
    }
    
    # Create extraction strategy
    extraction_strategy = JsonCssExtractionStrategy(schema, verbose=False)
    
    # Configure crawler
    config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        extraction_strategy=extraction_strategy,
    )
    
    async with AsyncWebCrawler(verbose=False) as crawler:
        result = await crawler.arun(
            url=publisher_transcript_url,
            config=config
        )
        
        if not result.success:
            print(f"Failed to extract transcript from {publisher_transcript_url}: {result.error_message}")
            return ""
            
        try:
            data = json.loads(result.extracted_content)
            if data and len(data) > 0:
                # Combine all paragraphs into a single text
                return "\n\n".join([item["paragraph_content"] for item in data])
            else:
                return ""
        except Exception as e:
            print(f"Error parsing transcript: {str(e)}")
            return ""
