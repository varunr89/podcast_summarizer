"""Handlers for processing messages from the Azure Service Bus queue."""
import httpx
import logging
from typing import Dict, Any
import uuid

logger = logging.getLogger(__name__)

async def passthrough_handler(payload: Dict[str, Any]):
    """
    A generic handler that passes the request payload to the appropriate HTTP endpoint.
    The payload should contain a "target_path" key indicating the endpoint path.
    
    Args:
        payload: Dictionary containing the request data and target_path
        
    Returns:
        The JSON response from the API endpoint
    
    Raises:
        ValueError: If target_path is missing or invalid
        httpx.HTTPError: If the HTTP request fails
    """
    message_id = payload.get("id", str(uuid.uuid4()))
    logger.critical(f"START handler for message {message_id}")

    # Get the target path from the payload
    target_path = payload.get("target_path")
    if not target_path:
        raise ValueError("Missing target_path in payload")
    
    # Remove target_path from the payload before forwarding
    request_data = {k: v for k, v in payload.items() if k != "target_path"}
    
    # Construct the full URL (using the same host as the running FastAPI app)
    url = f"http://localhost:80{target_path}"
    
    logger.info(f"Passthrough handler sending POST to {url}")
    logger.debug(f"Request payload: {request_data}")
    
    try:
        timeout = httpx.Timeout(10.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=request_data)
            logger.info(f"Passthrough request to {url} returned status {response.status_code}")
            
            # Raise an exception for non-success responses
            response.raise_for_status()
            return response.json()
        logger.critical(f"FINISH handler for message {message_id}")
    except httpx.ConnectError as e:
        logger.error(f"Connection error to {url}: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error making request to {url}: {str(e)}")
        raise