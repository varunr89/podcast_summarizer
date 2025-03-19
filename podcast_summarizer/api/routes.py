from fastapi import APIRouter
from .endpoints import podcast_routes, episode_routes, summarization_routes
from .common import logger

# Create main router
router = APIRouter()

# Include all sub-routers
router.include_router(podcast_routes.router, tags=["podcasts"])
router.include_router(episode_routes.router, tags=["episodes"])
router.include_router(summarization_routes.router, tags=["summarization"])

logger.info("API routes initialized")