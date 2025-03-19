from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List

from ..common import logger, handle_api_exception, get_db_instance

router = APIRouter()

@router.get("/episodes", response_model=List[Dict[str, Any]])
async def get_episodes(podcast_id: str = None, limit: int = 100, offset: int = 0):
    """
    Get a list of podcast episodes, optionally filtered by podcast ID.
    """
    logger.info(f"Fetching episodes (podcast_id={podcast_id}, limit={limit}, offset={offset})")
    
    try:
        db = get_db_instance()
        episodes = db.episode_manager.list(podcast_id=podcast_id, limit=limit, offset=offset)
        logger.info(f"Found {len(episodes)} episodes")
        return episodes
    except Exception as e:
        handle_api_exception(e, "fetching episodes")

@router.get("/episodes/{episode_id}", response_model=Dict[str, Any])
async def get_episode(episode_id: str, include_transcript: bool = False):
    """
    Get details for a specific episode.
    """
    logger.info(f"Fetching episode details for ID: {episode_id}")
    
    try:
        db = get_db_instance()
        episode = db.episode_manager.get(episode_id, include_transcript=include_transcript)
            
        if not episode:
            logger.warning(f"Episode not found with ID: {episode_id}")
            raise HTTPException(status_code=404, detail=f"Episode not found with ID: {episode_id}")
            
        logger.info(f"Successfully fetched episode: {episode.get('title', 'Unknown')}")
        return episode
    except Exception as e:
        handle_api_exception(e, "fetching episode details")

@router.get("/episodes/{episode_id}/transcript", response_model=Dict[str, Any])
async def get_episode_transcript(episode_id: str):
    """
    Get the transcript for a specific episode.
    """
    logger.info(f"Fetching transcript for episode ID: {episode_id}")
    
    try:
        db = get_db_instance()
        transcript = db.transcription_manager.get_episode_with_transcript(episode_id)
        
        if not transcript:
            logger.warning(f"Transcript not found for episode ID: {episode_id}")
            raise HTTPException(status_code=404, detail=f"Transcript not found for episode ID: {episode_id}")
            
        logger.debug(f"Successfully fetched transcript of length: {len(transcript)} characters")
        return {"episode_id": episode_id, "transcript": transcript}
    except Exception as e:
        handle_api_exception(e, "fetching transcript")
