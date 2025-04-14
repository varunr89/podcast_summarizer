"""
Functions for processing individual podcast episodes.
"""
import uuid
import os
import asyncio

from ...core.logging_config import get_logger
from ...core.config import get_settings
from ...processors.episode_processor import (
    check_audio_in_storage,
    get_audio_from_source,
)
from ...processors.audio import clean_audio_for_transcription

from .transcript_handler import get_existing_transcript, save_transcription, fetch_publisher_transcript

logger = get_logger(__name__)
settings = get_settings()

def sync_fetch_publisher_transcript(url):
    """Synchronous wrapper for the async fetch_publisher_transcript function."""
    loop = asyncio.get_event_loop()
    try:
        return loop.run_until_complete(fetch_publisher_transcript(url))
    except RuntimeError:
        # If there's no event loop in the current thread, create a new one
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            return new_loop.run_until_complete(fetch_publisher_transcript(url))
        finally:
            new_loop.close()

def process_single_episode(episode, podcast_id, temp_dir, storage, db, split_size_mb, keep_audio_files):
    """Process a single podcast episode."""
    logger.info(f"Processing episode: {episode['title']}")
    
    # Get or generate episode ID
    episode_id = episode.get("id", str(uuid.uuid4()))
    episode["id"] = episode_id # Ensure episode dict has the ID

    # Define blob names early for potential error logging
    podcast_uuid_segment = podcast_id[:8] if podcast_id else "unknown"
    episode_uuid_segment = episode_id[:8]
    transcript_blob_name = f"transcripts/{podcast_uuid_segment}_{episode_uuid_segment}_transcript.txt"
    audio_blob_name = f"audio/{podcast_uuid_segment}_{episode_uuid_segment}.mp3"

    try:
        # Check if this episode is already transcribed
        existing_episode = db.episode_manager.get(episode_id)
        if existing_episode and existing_episode.get("transcription_status") == "completed":
            logger.info(f"Episode {episode_id} already has completed transcription. Skipping processing.")
            return
        # If status is 'failed', maybe log and skip or retry? For now, proceed.
        elif existing_episode and existing_episode.get("transcription_status") == "failed":
            logger.warning(f"Episode {episode_id} previously failed. Re-attempting processing.")

        # Try to get existing transcript from DB (might be redundant if already checked status, but safe)
        full_transcription = get_existing_transcript(episode, db)
        
        if full_transcription:
            # Upload existing transcript if needed (e.g., if URL was missing)
            if "transcript_url" not in episode or not episode["transcript_url"]:
                try:
                    transcript_url = storage.upload_text(full_transcription, transcript_blob_name)
                    episode["transcript_url"] = transcript_url
                    logger.info(f"Uploaded existing transcript to blob storage: {transcript_url}")
                except Exception as e:
                    # Log warning but proceed to save what we have
                    logger.warning(f"Error uploading existing transcript text: {str(e)}")
        else:
            # No existing transcript found, proceed with generation
            publisher_transcript = None
            logger.info(f"Checking if we can use publisher provided transcript for {episode['title']}")
            if "publisher_transcript_url" in episode and episode["publisher_transcript_url"]:
                try:
                    publisher_transcript = sync_fetch_publisher_transcript(episode["publisher_transcript_url"])
                except Exception as e:
                    logger.warning(f"Failed to fetch publisher transcript: {str(e)}")
                
            if publisher_transcript:
                logger.info(f"Using publisher-provided transcript for episode: {episode['title']}")
                full_transcription = publisher_transcript
            else:
                # Get audio file and transcribe
                audio_file_path = check_audio_in_storage(
                    episode, audio_blob_name, storage, temp_dir, podcast_uuid_segment, episode_uuid_segment
                )
                
                if not audio_file_path:
                    audio_file_path = get_audio_from_source(episode, audio_blob_name, storage, temp_dir)
                    if not audio_file_path:
                        error_message = f"No audio source available for episode: {episode['title']}"
                        save_transcription(episode, podcast_id, None, transcript_blob_name,
                                           audio_blob_name, storage, db, keep_audio_files, error_message=error_message)
                        return # Stop processing this episode
                
                # Clean audio to remove silence, music, and other non-speech elements
                logger.info(f"Cleaning audio file to optimize for transcription: {audio_file_path}")
                cleaned_audio_path = clean_audio_for_transcription(audio_file_path)
                
                # Transcribe the cleaned audio
                from ...processors.episode_processor import transcribe_audio_file
                full_transcription = transcribe_audio_file(cleaned_audio_path, split_size_mb)
                if not full_transcription:
                    error_message = f"No transcription generated for episode: {episode['title']}"
                    save_transcription(episode, podcast_id, None, transcript_blob_name,
                                       audio_blob_name, storage, db, keep_audio_files, error_message=error_message)
                    return # Stop processing this episode
                
                # Clean up the cleaned audio file if it's different from the original
                if cleaned_audio_path != audio_file_path and os.path.exists(cleaned_audio_path):
                    try:
                        if not settings.CACHE_TEMP_FILES and not keep_audio_files:
                            os.remove(cleaned_audio_path)
                            logger.debug(f"Removed temporary cleaned audio file: {cleaned_audio_path}")
                    except Exception as e:
                        logger.warning(f"Failed to remove temporary cleaned audio file: {str(e)}")
        
        # Save successful results (or existing transcript if found and uploaded)
        save_transcription(episode, podcast_id, full_transcription, transcript_blob_name,
                           audio_blob_name, storage, db, keep_audio_files)

    except Exception as e:
        # Catch-all for any other unexpected error during processing
        error_message = f"Unexpected error processing episode {episode_id}: {str(e)}"
        logger.error(error_message, exc_info=True) # Log with traceback
        save_transcription(episode, podcast_id, None, transcript_blob_name,
                           audio_blob_name, storage, db, keep_audio_files, error_message=error_message)
