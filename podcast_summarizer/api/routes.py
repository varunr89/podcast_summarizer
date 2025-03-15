from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any
import uuid

from .models import PodcastFeedRequest, EpisodeSummaryRequest, PodcastUpsertRequest
from ..services.podcast_service import process_podcast_task
from ..services.podcast_db_service import update_existing_podcast, create_new_podcast
from ..processors.feed_parser import parse_podcast_feed
from ..core.database import get_db
from ..core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter()

@router.post("/process-podcast", response_model=dict)
async def process_podcast(request: PodcastFeedRequest, background_tasks: BackgroundTasks):
    """
    Process a podcast by first ensuring it exists in the database,
    then processing its episodes for transcription.
    """
    job_id = str(uuid.uuid4())
    logger.info(f"Received request to process podcast with job ID: {job_id}")
    try:
        # Check if podcast exists in database by feed URL
        db = get_db()
        existing_podcast = db.get_podcast_by_feed_url(request.feed_url)
        
        # If podcast doesn't exist or isn't active, upsert it first
        if not existing_podcast or existing_podcast.get("status") != "active":
            logger.info(f"Podcast not found or not active, upserting from feed: {request.feed_url}")
            # Parse the feed to get podcast data
            feed_data = parse_podcast_feed(request.feed_url)
            podcast_data = feed_data["podcast"]
            # Use the upsert_podcast function
            if existing_podcast:
                podcast_id = existing_podcast["id"]
                podcast_data["id"] = podcast_id
                db.upsert_podcast(podcast_data)
                logger.info(f"Updated existing podcast with ID: {podcast_id}")
            else:
                # Set initial status to processing
                podcast_data["status"] = "processing"
                podcast_id = db.upsert_podcast(podcast_data)
                # Add all episodes from the feed
                episode_count = 0
                for episode in feed_data["episodes"]:
                    episode["podcast_id"] = podcast_id
                    db.upsert_episode(episode)
                    episode_count += 1
                logger.info(f"Created new podcast with ID: {podcast_id} and added {episode_count} episodes")
                # Update podcast status to active
                db.client.table("podcasts").update({"status": "active"}).eq("id", podcast_id).execute()
        else:
            podcast_id = existing_podcast["id"]
            logger.info(f"Using existing active podcast with ID: {podcast_id}")
        
        # Update request with the podcast_id
        request.podcast_id = podcast_id

        # If both start_episode and episode_count are provided, convert to episode_indices for consistency
        if request.start_episode is not None and request.episode_count is not None and not request.episode_indices:
            start = request.start_episode
            end = start + request.episode_count - 1
            request.episode_indices = list(range(start, end + 1))
            logger.info(f"Converting start_episode={start} and episode_count={request.episode_count} to episode_indices={request.episode_indices}")
        
        # Start the background task
        background_tasks.add_task(process_podcast_task, request, job_id)
        
        return {
            "job_id": job_id, 
            "podcast_id": podcast_id,
            "status": "Processing started"
        }
    except Exception as e:
        logger.error(f"Error preparing podcast for processing: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process podcast: {str(e)}")

@router.post("/upsert-podcast", response_model=dict)
async def upsert_podcast(request: PodcastUpsertRequest):
    """
    Parse a podcast RSS feed and update the Supabase podcasts table.
    Only add new episodes if the podcast already exists.
    """
    try:
        logger.info(f"Received request to upsert podcast from feed: {request.feed_url}")
        # Parse the feed
        feed_data = parse_podcast_feed(request.feed_url)
        podcast_data = feed_data["podcast"]
        # Add custom description if provided
        if request.description:
            podcast_data["description"] = request.description
        
        # Check if podcast already exists
        db = get_db()
        existing_podcast = db.get_podcast_by_feed_url(request.feed_url)
        if existing_podcast:
            return update_existing_podcast(db, existing_podcast, podcast_data, feed_data["episodes"])
        else:
            return create_new_podcast(db, podcast_data, feed_data["episodes"])
            
    except ValueError as ve:
        logger.error(f"Invalid RSS feed: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error upserting podcast: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process podcast feed")

@router.post("/summarize-episode", response_model=dict)
async def summarize_episode(request: EpisodeSummaryRequest):
    """
    Generate a summary for a podcast episode with an existing transcription.
    
    Uses multiple summarization methods including langchain, llamaindex, spacy,
    and ensemble approaches.
    """
    logger.info(f"Received request to summarize episode with ID: {request.episode_id}, method: {request.method}")
    
    # Import here to avoid circular imports
    from ..services.summarizer_service import generate_episode_summary
    
    db = get_db()
    try:
        # Fetch transcription from database
        transcription = db.get_transcription(request.episode_id)
        if not transcription:
            logger.error(f"Transcription not found for episode ID: {request.episode_id}")
            raise HTTPException(status_code=404, detail="Transcription not found")
        
        # Generate summary using the enhanced summarizer service
        summary, key_points, highlights = generate_episode_summary(
            transcription, 
            request.custom_prompt,
            request.chunk_size, 
            request.chunk_overlap,
            request.detail_level,
            request.method,
            request.temperature
        )
        
        # Store additional metadata about the summarization method
        metadata = {
            "method": request.method,
            "detail_level": request.detail_level,
            "chunk_size": request.chunk_size,
            "chunk_overlap": request.chunk_overlap,
            "temperature": request.temperature
        }
        
        # Store the summary in the database
        record_id = db.store_summary(
            request.episode_id, 
            summary, 
            request.user_id,
            key_points, 
            highlights, 
            request.detail_level,
            metadata
        )
        
        logger.info(f"Summary stored with ID: {record_id}")
        return {
            "episode_id": request.episode_id, 
            "summary_id": record_id, 
            "status": "Summary stored",
            "method": request.method
        }
    except ValueError as ve:
        logger.error(f"Value error: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except ImportError as ie:
        logger.error(f"Import error: {str(ie)}")
        raise HTTPException(status_code=400, detail=f"The selected method requires additional dependencies: {str(ie)}")
    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")

@router.get("/summarization-methods", response_model=Dict[str, Any])
async def get_summarization_methods():
    """
    Get available summarization methods and their status
    """
    # Import to check availability
    from ..processors.langchain_summarizer import LLAMAINDEX_AVAILABLE
    from ..processors.spacy_transformer_summarizer import SPACY_TRANSFORMERS_AVAILABLE
    
    return {
        "methods": {
            "langchain": {
                "available": True,
                "description": "Uses LangChain map-reduce approach for effective summarization"
            },
            "llamaindex": {
                "available": LLAMAINDEX_AVAILABLE,
                "description": "Uses LlamaIndex hierarchical approach, ideal for long transcripts"
            },
            "spacy": {
                "available": SPACY_TRANSFORMERS_AVAILABLE,
                "description": "Uses spaCy and transformers for advanced NLP processing, ideal for speaker-heavy content"
            },
            "ensemble": {
                "available": True,
                "description": "Combines multiple methods for best results (requires more processing time)"
            },
            "auto": {
                "available": True,
                "description": "Automatically selects the best method based on transcript characteristics"
            }
        },
        "detail_levels": {
            "brief": "3-4 paragraph summary focused on essential points",
            "standard": "4-6 paragraph comprehensive summary",
            "detailed": "6-8 paragraph detailed summary with all significant topics"
        }
    }