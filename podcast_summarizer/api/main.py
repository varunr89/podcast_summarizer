"""Main FastAPI application module for the podcast summarizer API."""
import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from .routes import router
from ..core.config import get_settings
from .queue_processor import create_queue_processor, initialize_queue_processor

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown events."""
    try:
        # Load configuration
        settings = get_settings()

        # Create and initialize queue processor with direct parameter passing
        processor = create_queue_processor(
            connection_string=settings.SERVICE_BUS_CONNECTION_STRING,
            queue_name=settings.SERVICE_BUS_QUEUE_NAME,
            polling_interval=settings.QUEUE_POLLING_INTERVAL,
            max_cpu_percent=settings.MAX_CPU_USAGE,
            max_mem_percent=settings.MAX_MEM_USAGE
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

@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    """Middleware to measure and log endpoint execution time."""
    start_time = time.time()
    response = await call_next(request)
    elapsed_time = time.time() - start_time
    endpoint = request.url.path
    method = request.method
    logger.info(f"Endpoint '{endpoint}' ({method}) executed in {elapsed_time:.3f} seconds")
    return response

# Include the API routes
app.include_router(router)