"""Main FastAPI application module for the podcast summarizer API."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .routes import router
from ..core.config import get_settings
from .queue_processor import create_queue_processor, initialize_queue_processor
import logging

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown events."""
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
        logger.info(f"Initializing queue processor for queue: {settings.SERVICE_BUS_QUEUE_NAME}")
        processor = await initialize_queue_processor(processor)
        
        # Store the processor in app state to keep it alive
        app.state.queue_processor = processor
        
        logger.info(f"Queue processor initialized and listening to queue: {settings.SERVICE_BUS_QUEUE_NAME}")
        yield
    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        raise
    finally:
        # Cleanup phase
        logger.info("Application is shutting down. Performing cleanup.")
        if hasattr(app.state, "queue_processor"):
            await app.state.queue_processor.shutdown()
            logger.info("Queue processor shutdown completed")

# Create FastAPI app with lifespan handler
app = FastAPI(title="Podcast Processing API", lifespan=lifespan)

# Include the API routes
app.include_router(router)