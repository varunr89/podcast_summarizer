from fastapi import APIRouter
from .endpoints import podcast_routes, episode_routes, summarization_routes, email_routes
from .common import logger

# Create main router
router = APIRouter()

# Include all sub-routers
router.include_router(podcast_routes.router, tags=["podcasts"])
router.include_router(episode_routes.router, tags=["episodes"])
router.include_router(summarization_routes.router, tags=["summarization"])
router.include_router(email_routes.router, tags=["email"])

logger.info("API routes initialized")