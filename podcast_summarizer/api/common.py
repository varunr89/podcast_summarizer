from fastapi import HTTPException
from ..core.logging_config import get_logger
from ..core.database import get_db

logger = get_logger(__name__)

def handle_api_exception(e, operation_name, log_full_error=True):
    """Common exception handler for API routes"""
    if isinstance(e, HTTPException):
        raise e
    logger.error(f"Error {operation_name}: {str(e)}", exc_info=log_full_error)
    raise HTTPException(status_code=500, detail=f"Failed to {operation_name}: {str(e)}")

def get_db_instance():
    """Get database instance with error handling"""
    try:
        return get_db()
    except Exception as e:
        logger.error(f"Error connecting to database: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database connection error")
