"""
Processor for podcast episodes handling downloading, transcription, and resource management.
"""
import os
import uuid
import shutil
from pathlib import Path
from typing import List, Optional

from ..core.logging_config import get_logger
from ..core.config import get_settings
from ..core.azure_storage import get_storage
from .downloader import Episode, download_episode, download_episodes
from .transcriber import parse_audio_with_azure_openai
from .audio import split_audio_file, clean_audio_for_transcription

logger = get_logger(__name__)
settings = get_settings()

def download_podcast_episodes(
    feed_url: str,
    output_dir: Path,
    limit: Optional[int] = None,
    concurrent_downloads: Optional[int] = None,
    use_azure_storage: bool = False
) -> List[Path]:
    """Download podcast episodes from feed."""
    try:
        # Set concurrency
        if concurrent_downloads is None:
            concurrent_downloads = settings.MAX_CONCURRENT_DOWNLOADS

        # Get storage client
        storage = get_storage() if use_azure_storage else None
            
        # Download episodes
        downloaded_files = download_episodes(
            feed_url, output_dir, limit, concurrent_downloads, storage)
            
        logger.info(f"Downloaded {len(downloaded_files)} episodes")
        return downloaded_files
    except Exception as e:
        logger.error(f"Error downloading podcast: {str(e)}")
        return []

def check_audio_in_storage(episode, audio_blob_name, storage, temp_dir, podcast_uuid_segment, episode_uuid_segment):
    """Check if audio exists in storage and download if found."""
    logger.info(f"Checking if audio exists in storage {episode['id']}")
    try:
        if storage.blob_exists(audio_blob_name):
            audio_blob_url = storage.get_blob_url(audio_blob_name)
            logger.info(f"Audio file exists in storage: {audio_blob_url}")
            
            # Download for processing
            audio_file_path = storage.download_blob(audio_blob_name, temp_dir / f"{podcast_uuid_segment}_{episode_uuid_segment}.mp3")
            if audio_file_path:
                episode["audio_blob_url"] = audio_blob_url
                return audio_file_path
            else:
                logger.error(f"Failed to download existing audio from storage for {episode['title']}")
        else:
            logger.info(f"No existing audio found in storage for episode: {episode['title']}")
    except Exception as e:
        logger.warning(f"Error checking for existing audio in storage: {str(e)}")
    
    return None

def get_audio_from_source(episode, audio_blob_name, storage, temp_dir):
    """Get audio from source (local file or URL)."""
    logger.info(f"Getting audio from source for: {episode['title']}")
    
    # If we have an audio file path, process it directly
    if "audio_file_path" in episode:
        audio_file_path = Path(episode["audio_file_path"])
        # Upload to storage
        audio_blob_url = storage.upload_file(audio_file_path, audio_blob_name)
        episode["audio_blob_url"] = audio_blob_url
        logger.info(f"Uploaded audio from local path to storage: {audio_blob_url}")
        return audio_file_path
        
    # Download the audio if we have a URL
    elif "audio_url" in episode and episode["audio_url"]:
        ep_obj = Episode(
            title=episode["title"],
            url=episode["audio_url"],
            podcast_title=episode.get("podcast_title", "Unknown Podcast"),
            guid=episode.get("id", str(uuid.uuid4()))
        )
        audio_file_path = download_episode(ep_obj, temp_dir)
        if audio_file_path:
            # Upload to storage
            audio_blob_url = storage.upload_file(audio_file_path, audio_blob_name)
            episode["audio_blob_url"] = audio_blob_url
            logger.info(f"Downloaded and uploaded audio from URL: {audio_blob_url}")
            return audio_file_path
        else:
            logger.error(f"Failed to download episode from URL: {episode['title']}")
    
    return None

def transcribe_audio_file(audio_file_path, split_size_mb):
    """Transcribe audio file and return full transcription."""
    try:
        # Validate input
        if not audio_file_path or not os.path.exists(audio_file_path):
            logger.error(f"Invalid audio file path: {audio_file_path}")
            return None
            
        # Check if file appears to be already cleaned (contains "_cleaned" in the filename)
        file_path = Path(audio_file_path)
        if "_cleaned" in file_path.stem:
            logger.info(f"Audio file appears to be already cleaned: {audio_file_path}")
            cleaned_audio = audio_file_path
        else:
            # Clean audio for better transcription
            logger.info(f"Cleaning audio for transcription: {audio_file_path}")
            cleaned_audio = clean_audio_for_transcription(audio_file_path)
        
        if not cleaned_audio:
            logger.warning("Audio cleaning failed, using original file")
            cleaned_audio = audio_file_path
            
        # Verify the cleaned audio file exists
        if not os.path.exists(cleaned_audio):
            logger.warning(f"Cleaned audio file not found, using original: {audio_file_path}")
            cleaned_audio = audio_file_path
        
        # Split audio file into chunks
        logger.info(f"Splitting audio file: {cleaned_audio}")
        chunks = split_audio_file(cleaned_audio, split_size_mb)
        
        if not chunks:
            logger.error("Failed to split audio file")
            return None
            
        # Get settings for transcription
        api_key = settings.WHISPER_API_KEY
        api_version = settings.WHISPER_API_VERSION
        endpoint = str(settings.WHISPER_ENDPOINT)  # Convert HttpUrl to string
        deployment_name = settings.WHISPER_DEPLOYMENT_NAME
        
        # Use the new transcribe_audio function that tries local first
        from .transcriber import transcribe_audio
        docs = transcribe_audio(
            chunks,
            use_local_first=settings.USE_LOCAL_WHISPER_FIRST, 
            local_model_size=settings.LOCAL_WHISPER_MODEL,
            azure_api_key=api_key,
            azure_api_version=api_version,
            azure_endpoint=endpoint,
            azure_deployment_name=deployment_name
        )
        
        transcription = "\n".join(doc.get("content", "") for doc in docs)
        
        # Clean up chunks
        for chunk in chunks:
            try:
                if os.path.exists(chunk):
                    os.remove(chunk)
            except Exception as e:
                logger.warning(f"Error cleaning up chunk file {chunk}: {str(e)}")
        
        # Clean up cleaned audio if it's different from original
        if cleaned_audio != audio_file_path:
            try:
                if os.path.exists(cleaned_audio):
                    os.remove(cleaned_audio)
            except Exception as e:
                logger.warning(f"Error cleaning up processed audio file {cleaned_audio}: {str(e)}")
        
        return transcription
    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}", exc_info=True)
        return None

def cleanup_resources(temp_dir):
    """Clean up temporary resources."""
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.info(f"Removed temporary directory: {temp_dir}")
    except Exception as e:
        logger.warning(f"Error cleaning up temporary directory: {str(e)}")
