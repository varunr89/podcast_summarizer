"""Main FastAPI application module for the podcast summarizer API."""
import logging
from fastapi import FastAPI
from .routes import router
from ..core.config import get_settings
from .queue_processor import create_queue_processor, initialize_queue_processor

# Configure logging
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Podcast Processing API")

# Include the API routes
app.include_router(router)

@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    try:
        # Load configuration
        settings = get_settings()
        
        # Create and initialize queue processor
        processor = create_queue_processor(
            connection_string=settings.SERVICE_BUS_CONNECTION_STRING,
            queue_name=settings.SERVICE_BUS_QUEUE_NAME
        )
        
        # Register the passthrough handler as a generic handler for all requests
        from .handlers import passthrough_handler
        processor.dispatcher.register_handler("default", passthrough_handler)
        
        # Start queue processing
        await initialize_queue_processor(processor)
        
        logger.info("Application started successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        raise
