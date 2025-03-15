"""
Service for processing podcast episodes, including downloading, transcribing, and managing storage.
"""
import os
import time
import uuid
import shutil
from pathlib import Path

from ..api.models import PodcastFeedRequest
from ..core.database import get_db
from ..core.logging_config import get_logger
from ..core.azure_storage import get_storage
from ..core.config import get_settings
from ..processors.downloader import Episode, download_episode
from ..processors.downloader_service import download_podcast
from ..processors.transcriber import parse_audio_with_azure_openai
from ..processors.audio import split_audio_file

logger = get_logger(__name__)
settings = get_settings()

def process_podcast_task(request: PodcastFeedRequest, job_id: str):
    """
    Background task to process a podcast feed, download episodes, and generate transcriptions.
    
    Args:
        request: The podcast processing request
        job_id: Unique identifier for this job
    """
    try:
        # Create a unique temp directory for this job
        temp_dir = Path(settings.TEMP_DIR) / f"job_{job_id[:8]}"
        os.makedirs(temp_dir, exist_ok=True)
        logger.info(f"Starting podcast processing task with job ID: {job_id} using temp dir: {temp_dir}")
        
        # Get Azure Blob Storage client
        storage = get_storage()
        
        # Get the podcast ID from the request
        podcast_id = request.podcast_id
        
        # Get episode information from the database if podcast_id is provided
        db = get_db()
        episode_data = []
        
        if podcast_id:
            # Get existing episodes from the database
            episodes = db.list_episodes(podcast_id)
            
            # Filter episodes based on request parameters
            if episodes:
                episodes = filter_episodes(episodes, request)
                
            for episode in episodes:
                # Add episode ID if it doesn't exist
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
        
        # If no episode data found, fallback to downloading from feed
        if not episode_data:
            episode_data = download_episodes_from_feed(request, temp_dir)
        
        # Process each episode
        for episode in episode_data:
            process_single_episode(episode, podcast_id, temp_dir, storage, db, request.split_size_mb, request.keep_audio_files)
            
        logger.info(f"Job {job_id} completed: processed {len(episode_data)} episodes.")
        
        # More thorough cleanup of the temporary directory
        cleanup_temp_directory(temp_dir)
        
    except Exception as e:
        logger.error(f"Error in processing podcast: {str(e)}", exc_info=True)

def filter_episodes(episodes, request):
    """
    Filter episodes based on the request parameters.
    
    Args:
        episodes: List of episodes
        request: Request containing filter parameters
        
    Returns:
        Filtered list of episodes
    """
    if request.episode_indices:
        # Filter episodes by requested indices
        selected_episodes = []
        for idx in request.episode_indices:
            # Adjust for 1-based indexing (assuming user provides natural 1-based indices)
            idx_zero_based = idx - 1
            if 0 <= idx_zero_based < len(episodes):
                selected_episodes.append(episodes[idx_zero_based])
            else:
                logger.warning(f"Episode index {idx} is out of range (1-{len(episodes)})")
        return selected_episodes
    # Handle start_episode and episode_count parameters if provided
    elif request.start_episode is not None:
        start_idx = request.start_episode - 1  # Convert to 0-based
        if start_idx < 0:
            start_idx = 0
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
    """
    Download episodes from a podcast feed.
    
    Args:
        request: The podcast processing request
        temp_dir: Directory to save downloaded files
        
    Returns:
        List of episode data dictionaries
    """
    # Download all episodes first so we can access them by index
    temp_files = download_podcast(request.feed_url, temp_dir, limit=None)
    
    # Filter episodes by index if specified
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
    
    episode_data = []
    # Process the selected files
    for file in temp_files:
        logger.info(f"Processing file: {file}")
        # Generate a new episode ID
        episode_id = str(uuid.uuid4())
        # Extract episode info from filename
        episode_data.append({
            "id": episode_id,
            "podcast_id": request.podcast_id,
            "title": Path(file).stem,
            "audio_file_path": str(file)
        })
    
    return episode_data

def process_single_episode(episode, podcast_id, temp_dir, storage, db, split_size_mb, keep_audio_files):
    """
    Process a single podcast episode: transcribe audio and store the results.
    
    Args:
        episode: Episode data dictionary
        podcast_id: ID of the podcast
        temp_dir: Directory to save temporary files
        storage: Azure storage client
        db: Database connection
        split_size_mb: Size to split audio files
        keep_audio_files: Whether to keep audio files after processing
    """
    logger.info(f"Processing episode: {episode['title']}")
    
    # Get episode ID (or generate one if missing)
    episode_id = episode.get("id", str(uuid.uuid4()))
    episode["id"] = episode_id
    
    # Generate file names based on UUIDs
    podcast_uuid_segment = podcast_id[:8] if podcast_id else "unknown"
    episode_uuid_segment = episode_id[:8]
    
    # Define transcript blob name and audio blob name
    transcript_blob_name = f"transcripts/{podcast_uuid_segment}_{episode_uuid_segment}_transcript.txt"
    audio_blob_name = f"audio/{podcast_uuid_segment}_{episode_uuid_segment}.mp3"
    
    # Check if transcript already exists in database
    existing_transcript = None
    if "id" in episode:
        try:
            existing_episode = db.get_episode_with_transcript(episode["id"])
            if existing_episode and "transcript" in existing_episode and existing_episode["transcript"]:
                existing_transcript = existing_episode["transcript"]
                logger.info(f"Found existing transcript for episode {episode['id']}")
        except Exception as e:
            logger.warning(f"Error checking for existing transcript: {str(e)}")
    
    # If transcript exists, use it and skip audio processing
    if existing_transcript:
        logger.info(f"Using existing transcript for episode: {episode['title']}")
        full_transcription = existing_transcript
        
        # Ensure transcript is in blob storage
        try:
            # Generate transcript URL if not already set
            if "transcript_url" not in episode or not episode["transcript_url"]:
                transcript_url = storage.upload_text(full_transcription, transcript_blob_name)
                episode["transcript_url"] = transcript_url
                logger.info(f"Uploaded existing transcript to blob storage: {transcript_url}")
        except Exception as e:
            logger.warning(f"Error handling existing transcript: {str(e)}")
    else:
        # No transcript, check if audio exists in storage
        audio_file_path = check_audio_in_storage(episode, audio_blob_name, storage, temp_dir, podcast_uuid_segment, episode_uuid_segment)
        
        # If audio doesn't exist in storage, get it from source
        if not audio_file_path:
            audio_file_path = get_audio_from_source(episode, audio_blob_name, storage, temp_dir)
            if not audio_file_path:
                logger.error(f"No audio source available for episode: {episode['title']}")
                return
        
        # Transcribe the audio
        full_transcription = transcribe_audio(audio_file_path, split_size_mb)
        if not full_transcription:
            logger.error(f"No transcription generated for episode: {episode['title']}")
            return
    
    # Process the transcript (whether existing or newly generated)
    save_transcription(episode, podcast_id, full_transcription, transcript_blob_name, audio_blob_name, 
                      storage, db, keep_audio_files)
    
    # Ensure we have a published_date field
    if "published_date" not in episode and "published_at" in episode:
        episode["published_date"] = episode["published_at"]
    elif "published_date" not in episode and "published_at" not in episode:
        episode["published_date"] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

def check_audio_in_storage(episode, audio_blob_name, storage, temp_dir, podcast_uuid_segment, episode_uuid_segment):
    """
    Check if audio exists in storage and download if found.
    
    Args:
        episode: Episode data dictionary
        audio_blob_name: Blob name for audio
        storage: Azure storage client
        temp_dir: Directory to save downloaded file
        podcast_uuid_segment: Podcast UUID segment for filename
        episode_uuid_segment: Episode UUID segment for filename
    
    Returns:
        Path to downloaded audio file if found, None otherwise
    """
    logger.info(f"Checking if audio exists in storage {episode['id']}")
    audio_file_path = None
    try:
        audio_blob_exists = storage.blob_exists(audio_blob_name)
        if audio_blob_exists:
            audio_blob_url = storage.get_blob_url(audio_blob_name)
            logger.info(f"Audio file exists in storage, will use for processing: {audio_blob_url}")
            
            # Download the audio for processing
            audio_file_path = storage.download_blob(audio_blob_name, temp_dir / f"{podcast_uuid_segment}_{episode_uuid_segment}.mp3")
            if audio_file_path:
                episode["audio_blob_url"] = audio_blob_url
            else:
                logger.error(f"Failed to download existing audio from storage for {episode['title']}")
        else:
            logger.info(f"No existing audio found in storage for episode: {episode['title']}")
    except Exception as e:
        logger.warning(f"Error checking for existing audio in storage: {str(e)}")
    
    return audio_file_path

def get_audio_from_source(episode, audio_blob_name, storage, temp_dir):
    """
    Get audio from source (local file or URL).
    
    Args:
        episode: Episode data dictionary
        audio_blob_name: Blob name for audio
        storage: Azure storage client
        temp_dir: Directory to save downloaded file
        
    Returns:
        Path to audio file if obtained, None otherwise
    """
    logger.info(f"Getting audio from source for: {episode['title']}")
    audio_file_path = None
    
    # If we have an audio file path, process it directly
    if "audio_file_path" in episode:
        audio_file_path = Path(episode["audio_file_path"])
        # Upload original audio file to Azure Blob Storage
        audio_blob_url = storage.upload_file(audio_file_path, audio_blob_name)
        episode["audio_blob_url"] = audio_blob_url
        logger.info(f"Uploaded audio from local path to storage: {audio_blob_url}")
    # Otherwise, download the audio first if we have a URL
    elif "audio_url" in episode and episode["audio_url"]:
        ep_obj = Episode(
            title=episode["title"],
            audio_url=episode["audio_url"]
        )
        audio_file_path = download_episode(ep_obj, temp_dir)
        if audio_file_path:
            # Upload to Azure Blob Storage
            audio_blob_url = storage.upload_file(audio_file_path, audio_blob_name)
            episode["audio_blob_url"] = audio_blob_url
            logger.info(f"Downloaded and uploaded audio from URL to storage: {audio_blob_url}")
        else:
            logger.error(f"Failed to download episode from source URL: {episode['title']}")
    
    return audio_file_path

def transcribe_audio(audio_file_path, split_size_mb):
    """
    Transcribe an audio file.
    
    Args:
        audio_file_path: Path to the audio file
        split_size_mb: Size to split audio files in MB
        
    Returns:
        Full transcription text or None if error
    """
    try:
        # Split and process audio file
        chunks = split_audio_file(audio_file_path, split_size_mb)
        
        # Process audio chunks with Whisper
        api_key = settings.WHISPER_API_KEY
        api_version = settings.WHISPER_API_VERSION
        endpoint = settings.WHISPER_ENDPOINT
        deployment_name = settings.WHISPER_DEPLOYMENT_NAME
        
        docs = parse_audio_with_azure_openai(chunks, api_key, api_version, endpoint, deployment_name)
        full_transcription = "\n".join(doc.get("content", "") for doc in docs)
        
        # Clean up temporary audio chunks
        for chunk in chunks:
            try:
                if os.path.exists(chunk):
                    os.remove(chunk)
            except Exception as e:
                logger.warning(f"Error cleaning up chunk file {chunk}: {str(e)}")
        
        return full_transcription
    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}")
        return None

def save_transcription(episode, podcast_id, full_transcription, transcript_blob_name, audio_blob_name, 
                      storage, db, keep_audio_files):
    """
    Save transcription to storage and database.
    
    Args:
        episode: Episode data dictionary
        podcast_id: ID of the podcast
        full_transcription: Transcription text
        transcript_blob_name: Blob name for transcript
        audio_blob_name: Blob name for audio
        storage: Azure storage client
        db: Database connection
        keep_audio_files: Whether to keep audio files after processing
    """
    # Ensure episode has podcast_id before storing transcription
    if "podcast_id" not in episode or not episode["podcast_id"]:
        episode["podcast_id"] = podcast_id
    
    # Upload transcript to Azure Blob Storage
    transcript_url = storage.upload_text(full_transcription, transcript_blob_name)
    episode["transcript_url"] = transcript_url
    
    # Store the transcription and blob URL in the database
    try:
        db.store_transcription(episode, full_transcription)
        logger.info(f"Transcription completed and stored for episode: {episode['title']}")
        
        # Delete the audio file from storage now that transcript is complete
        # Only delete if we uploaded it to Azure (i.e., we have an audio_blob_url)
        if "audio_blob_url" in episode and not keep_audio_files:
            try:
                storage.delete_blob(audio_blob_name)
                logger.info(f"Deleted audio file from storage: {audio_blob_name}")
            except Exception as e:
                logger.warning(f"Failed to delete audio file from storage: {str(e)}")
    except ValueError as ve:
        logger.error(f"Failed to store transcription - validation error: {str(ve)}")
        logger.error(f"Episode data: {episode}")
    except Exception as e:
        logger.error(f"Failed to store transcription: {str(e)}")

def cleanup_temp_directory(temp_dir):
    """
    Clean up temporary directory.
    
    Args:
        temp_dir: Directory to clean up
    """
    if not settings.CACHE_TEMP_FILES:
        try:
            # Use shutil.rmtree for more complete directory cleanup
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"Removed temporary directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"Error cleaning up temporary directory: {str(e)}")
    else:
        logger.info(f"Keeping temporary files in: {temp_dir}")
