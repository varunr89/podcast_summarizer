from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from ..models import EpisodeSummaryRequest
from ..common import logger, handle_api_exception, get_db_instance
from ...processors.summarization import SummaryResult

router = APIRouter()

@router.post("/summarize-episode", response_model=dict)
async def summarize_episode(request: EpisodeSummaryRequest):
    """
    Generate a summary for a podcast episode with an existing transcription.
    """
    logger.info(f"Received request to summarize episode with ID: {request.episode_id}, method: {request.method}")
    
    # Import here to avoid circular imports
    from ...services.summarizer_service import generate_episode_summary
    
    try:
        db = get_db_instance()
        # Check for existing summary to avoid unnecessary recomputation/cost
        existing = db.summary_manager.get(request.episode_id)
        if existing:
            logger.info(f"Using cached summary for episode ID: {request.episode_id}")
            return {
                "episode_id": existing.get("episode_id"),
                "summary_id": existing.get("id"),
                "status": "Summary retrieved",
                "method": request.method,
                "summary_preview": (existing.get("summary") or "")[:200] + ("..." if existing.get("summary") and len(existing.get("summary")) > 200 else ""),
                "key_points_count": len(existing.get("key_points") or []),
                "highlights_count": len(existing.get("highlights") or [])
            }

        # Fetch transcription directly - no need to query episode details first
        transcription = db.transcription_manager.get(request.episode_id)
        if not transcription:
            logger.error(f"Transcription not found for episode ID: {request.episode_id}")
            raise HTTPException(status_code=404, detail="Transcription not found")
        
        # Generate summary using the enhanced summarizer service
        logger.debug(f"Starting summarization for episode {request.episode_id} with method {request.method}")
        
        # Unpack the tuple returned by generate_episode_summary
        summary, key_points, highlights = generate_episode_summary(
            transcription=transcription,
            config=request
        )
        
        # Store the summary in the database
        logger.debug(f"Storing summary for episode {request.episode_id}")
        record_id = db.summary_manager.store(
            request.episode_id,
            summary,
            request.user_id,
            key_points.get("points", []),
            highlights,
            request.detail_level,
            {}  # Empty metadata as it's not returned by the function
        )
        
        logger.info(f"Summary stored with ID: {record_id}")
        return {
            "episode_id": request.episode_id,
            "summary_id": record_id,
            "status": "Summary stored",
            "method": request.method,
            # Include key summary data in response to save a separate API call
            "summary_preview": summary[:200] + ("..." if len(summary) > 200 else ""),
            "key_points_count": len(key_points.get("points", [])),
            "highlights_count": len(highlights)
        }
    except ValueError as ve:
        logger.error(f"Value error: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except ImportError as ie:
        logger.error(f"Import error: {str(ie)}")
        raise HTTPException(status_code=400, detail=f"The selected method requires additional dependencies: {str(ie)}")
    except Exception as e:
        handle_api_exception(e, "generating summary")

@router.get("/summarization-methods", response_model=Dict[str, Any])
async def get_summarization_methods():
    """
    Get available summarization methods and their status
    """
    # Import to check availability - use centralized service for better organization
    from ...services.summarizer_service import get_available_summarization_methods
    
    # Get methods and details from the refactored service
    methods = get_available_summarization_methods()
    
    return {
        "methods": methods,
        "detail_levels": {
            "brief": "3-4 paragraph summary focused on essential points",
            "standard": "4-6 paragraph comprehensive summary",
            "detailed": "6-8 paragraph detailed summary with all significant topics"
        }
    }
