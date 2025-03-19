from fastapi import APIRouter, HTTPException, BackgroundTasks
import uuid

from ..models import PodcastFeedRequest, PodcastUpsertRequest
from ...services.podcast_service import process_podcast_task
from ...services.podcast_db_service import update_existing_podcast, create_new_podcast
from ...processors.feed_parser import parse_podcast_feed
from ..common import logger, handle_api_exception, get_db_instance

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
        db = get_db_instance()
        existing_podcast = db.podcast_manager.get_by_feed_url(request.feed_url)
        
        # If podcast doesn't exist or isn't active, upsert it first
        if not existing_podcast or existing_podcast.get("status") != "active":
            logger.info(f"Podcast not found or not active, upserting from feed: {request.feed_url}")
            # Parse the feed to get podcast data
            feed_data = parse_podcast_feed(request.feed_url)
            podcast_data = feed_data["podcast"]
            
            # Use the service functions for upserting podcasts
            if existing_podcast:
                result = update_existing_podcast(db, existing_podcast, podcast_data, feed_data["episodes"])
                podcast_id = result["podcast_id"]
                logger.info(f"Updated existing podcast with ID: {podcast_id}")
            else:
                # Service function handles creation and episode insertion
                result = create_new_podcast(db, podcast_data, feed_data["episodes"])
                podcast_id = result["podcast_id"]
                logger.info(f"Created new podcast with ID: {podcast_id} with {result['episodes_added']} episodes")
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
        handle_api_exception(e, "preparing podcast for processing")

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
        db = get_db_instance()
        existing_podcast = db.podcast_manager.get_by_feed_url(request.feed_url)
        if existing_podcast:
            # Make sure to include the ID of the existing podcast in podcast_data
            podcast_data["id"] = existing_podcast["id"]
            logger.info(f"Updating existing podcast with ID: {existing_podcast['id']}")
            return update_existing_podcast(db, existing_podcast, podcast_data, feed_data["episodes"])
        else:
            logger.info(f"Creating new podcast from feed: {request.feed_url}")
            return create_new_podcast(db, podcast_data, feed_data["episodes"])
            
    except ValueError as ve:
        logger.error(f"Invalid RSS feed: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        handle_api_exception(e, "upserting podcast")
