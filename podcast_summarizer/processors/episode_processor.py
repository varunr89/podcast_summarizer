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
from .audio import split_audio_file

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
        # Split audio file into chunks
        chunks = split_audio_file(audio_file_path, split_size_mb)
        
        # Process with Whisper
        api_key = settings.WHISPER_API_KEY
        api_version = settings.WHISPER_API_VERSION
        endpoint = str(settings.WHISPER_ENDPOINT)  # Convert HttpUrl to string
        deployment_name = settings.WHISPER_DEPLOYMENT_NAME
        
        docs = parse_audio_with_azure_openai(chunks, api_key, api_version, endpoint, deployment_name)
        transcription = "\n".join(doc.get("content", "") for doc in docs)
        
        # Clean up chunks
        for chunk in chunks:
            try:
                if os.path.exists(chunk):
                    os.remove(chunk)
            except Exception as e:
                logger.warning(f"Error cleaning up chunk file {chunk}: {str(e)}")
        
        return transcription
    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}")
        return None

def cleanup_resources(temp_dir):
    """Clean up temporary resources."""
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.info(f"Removed temporary directory: {temp_dir}")
    except Exception as e:
        logger.warning(f"Error cleaning up temporary directory: {str(e)}")
