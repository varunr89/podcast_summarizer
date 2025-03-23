"""
Service for processing podcast episodes, including downloading, transcribing, and managing storage.
"""
import os
import time
import uuid
from pathlib import Path

from ..api.models import PodcastFeedRequest
from ..core.database import get_db
from ..core.logging_config import get_logger
from ..core.azure_storage import get_storage
from ..core.config import get_settings
from ..processors.episode_processor import (
    download_podcast_episodes,
    transcribe_audio_file,
    check_audio_in_storage,
    get_audio_from_source,
    cleanup_resources
)
from ..processors.audio import clean_audio_for_transcription

logger = get_logger(__name__)
settings = get_settings()

def process_podcast_task(request: PodcastFeedRequest, job_id: str):
    """
    Background task to process a podcast feed, download episodes, and generate transcriptions.
    """
    try:
        # Create a unique temp directory for this job
        temp_dir = Path(settings.TEMP_DIR) / f"job_{job_id[:8]}"
        os.makedirs(temp_dir, exist_ok=True)
        logger.info(f"Starting podcast processing task with job ID: {job_id} using temp dir: {temp_dir}")
        
        # Get dependencies
        storage = get_storage()
        db = get_db()
        podcast_id = request.podcast_id
        
        # Get episode data
        episode_data = get_episode_data(request, podcast_id, db, temp_dir)
        
        # Process each episode
        for episode in episode_data:
            process_single_episode(
                episode, 
                podcast_id, 
                temp_dir, 
                storage, 
                db, 
                request.split_size_mb, 
                request.keep_audio_files
            )
            
        logger.info(f"Job {job_id} completed: processed {len(episode_data)} episodes.")
        
        # Cleanup
        if not settings.CACHE_TEMP_FILES:
            cleanup_resources(temp_dir)
        
    except Exception as e:
        logger.error(f"Error in processing podcast: {str(e)}", exc_info=True)

def get_episode_data(request, podcast_id, db, temp_dir):
    """Get episode data from database or feed."""
    episode_data = []
    
    # Try to get episodes from database first
    if podcast_id:
        episodes = db.episode_manager.list(podcast_id)
        if episodes:
            episodes = filter_episodes(episodes, request)
            
            for episode in episodes:
                if "id" not in episode or not episode["id"]:
                    episode["id"] = str(uuid.uuid4())
                
                episode_data.append({
                    "id": episode.get("id"),
                    "podcast_id": podcast_id,
                    "title": episode.get("title", "Unknown Episode"),
                    "published_date": episode.get("published_at"),
                    "audio_url": episode.get("audio_url", ""),
                    "transcript_url": episode.get("transcript_url", None)
                })
    
    # If no episode data found, download from feed
    if not episode_data:
        episode_data = download_episodes_from_feed(request, temp_dir)
    
    return episode_data

def filter_episodes(episodes, request):
    """Filter episodes based on request parameters."""
    if request.episode_indices:
        # Filter episodes by requested indices
        selected_episodes = []
        for idx in request.episode_indices:
            idx_zero_based = idx - 1
            if 0 <= idx_zero_based < len(episodes):
                selected_episodes.append(episodes[idx_zero_based])
            else:
                logger.warning(f"Episode index {idx} is out of range (1-{len(episodes)})")
        return selected_episodes
    
    elif request.start_episode is not None:
        start_idx = max(0, request.start_episode - 1)
        if start_idx >= len(episodes):
            logger.warning(f"Start episode {request.start_episode} is out of range, using first episode")
            start_idx = 0
            
        end_idx = len(episodes)
        if request.episode_count is not None:
            end_idx = min(start_idx + request.episode_count, len(episodes))
        
        logger.info(f"Processing episodes {start_idx+1}-{end_idx} (of {len(episodes)} total episodes)")
        return episodes[start_idx:end_idx]
    
    elif request.limit_episodes:
        return episodes[:request.limit_episodes]
    
    return episodes

def download_episodes_from_feed(request, temp_dir):
    """Download episodes from a podcast feed."""
    # Download episodes
    temp_files = download_podcast_episodes(request.feed_url, temp_dir)
    
    # Filter episodes
    if request.episode_indices and temp_files:
        selected_files = []
        for idx in request.episode_indices:
            idx_zero_based = idx - 1
            if 0 <= idx_zero_based < len(temp_files):
                selected_files.append(temp_files[idx_zero_based])
            else:
                logger.warning(f"Episode index {idx} is out of range (1-{len(temp_files)})")
        temp_files = selected_files
    elif request.limit_episodes:
        temp_files = temp_files[:request.limit_episodes]
    
    # Create episode data objects
    episode_data = []
    for file in temp_files:
        logger.info(f"Processing file: {file}")
        episode_data.append({
            "id": str(uuid.uuid4()),
            "podcast_id": request.podcast_id,
            "title": Path(file).stem,
            "audio_file_path": str(file)
        })
    
    return episode_data

def process_single_episode(episode, podcast_id, temp_dir, storage, db, split_size_mb, keep_audio_files):
    """Process a single podcast episode."""
    logger.info(f"Processing episode: {episode['title']}")
    
    # Get or generate episode ID
    episode_id = episode.get("id", str(uuid.uuid4()))
    episode["id"] = episode_id
    
    # Check if this episode is already transcribed
    try:
        existing_episode = db.episode_manager.get(episode_id)
        if existing_episode and existing_episode.get("transcription_status") == "completed":
            logger.info(f"Episode {episode_id} already has completed transcription. Skipping processing.")
            return
    except Exception as e:
        logger.warning(f"Error checking transcription status: {str(e)}")
    
    # Define blob names
    podcast_uuid_segment = podcast_id[:8] if podcast_id else "unknown"
    episode_uuid_segment = episode_id[:8]
    transcript_blob_name = f"transcripts/{podcast_uuid_segment}_{episode_uuid_segment}_transcript.txt"
    audio_blob_name = f"audio/{podcast_uuid_segment}_{episode_uuid_segment}.mp3"
    
    # Try to get existing transcript
    full_transcription = get_existing_transcript(episode, db)
    
    if full_transcription:
        # Upload existing transcript if needed
        if "transcript_url" not in episode or not episode["transcript_url"]:
            try:
                transcript_url = storage.upload_text(full_transcription, transcript_blob_name)
                episode["transcript_url"] = transcript_url
                logger.info(f"Uploaded existing transcript to blob storage: {transcript_url}")
            except Exception as e:
                logger.warning(f"Error handling existing transcript: {str(e)}")
    else:
        # Get audio file and transcribe
        audio_file_path = check_audio_in_storage(
            episode, audio_blob_name, storage, temp_dir, podcast_uuid_segment, episode_uuid_segment
        )
        
        if not audio_file_path:
            audio_file_path = get_audio_from_source(episode, audio_blob_name, storage, temp_dir)
            if not audio_file_path:
                logger.error(f"No audio source available for episode: {episode['title']}")
                return
        
        # Clean audio to remove silence, music, and other non-speech elements
        logger.info(f"Cleaning audio file to optimize for transcription: {audio_file_path}")
        cleaned_audio_path = clean_audio_for_transcription(audio_file_path)
        
        # Transcribe the cleaned audio
        full_transcription = transcribe_audio_file(cleaned_audio_path, split_size_mb)
        if not full_transcription:
            logger.error(f"No transcription generated for episode: {episode['title']}")
            return
        
        # Clean up the cleaned audio file if it's different from the original
        if cleaned_audio_path != audio_file_path and os.path.exists(cleaned_audio_path):
            try:
                if not settings.CACHE_TEMP_FILES and not keep_audio_files:
                    os.remove(cleaned_audio_path)
                    logger.debug(f"Removed temporary cleaned audio file: {cleaned_audio_path}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary cleaned audio file: {str(e)}")
    
    # Save results
    save_transcription(episode, podcast_id, full_transcription, transcript_blob_name, 
                       audio_blob_name, storage, db, keep_audio_files)

def get_existing_transcript(episode, db):
    """Get existing transcript from the database if available."""
    if "id" in episode:
        try:
            existing_episode = db.episode_manager.get(episode["id"])
            if existing_episode and "transcript" in existing_episode and existing_episode["transcript"]:
                logger.info(f"Found existing transcript for episode {episode['id']}")
                return existing_episode["transcript"]
        except Exception as e:
            logger.warning(f"Error checking for existing transcript: {str(e)}")
    return None

def save_transcription(episode, podcast_id, transcription, transcript_blob_name, 
                      audio_blob_name, storage, db, keep_audio_files):
    """Save transcription to storage and database."""
    # Ensure episode has podcast_id
    if "podcast_id" not in episode or not episode["podcast_id"]:
        episode["podcast_id"] = podcast_id
    
    # Upload transcript
    transcript_url = storage.upload_text(transcription, transcript_blob_name)
    episode["transcript_url"] = transcript_url
    
    # Ensure published_date exists
    if "published_date" not in episode:
        episode["published_date"] = episode.get("published_at", time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    
    # Set transcription status to completed
    episode["transcription_status"] = "completed"
    
    # Store in database
    try:
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
        logger.error(f"Failed to store transcription: {str(e)}")
