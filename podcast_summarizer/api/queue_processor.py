"""Azure Service Bus queue processor and message dispatcher for the podcast summarizer API."""
import json
import logging
import asyncio
from typing import Dict, Any, Callable, Optional
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage

# Configure logging
logger = logging.getLogger(__name__)

class QueueProcessorError(Exception):
    """Custom exception for queue processing errors."""
    pass

class MessageDispatcher:
    """Handles dispatching of messages to appropriate handlers based on routing information."""
    
    def __init__(self):
        self.handlers: Dict[str, Callable] = {}
        
    def register_handler(self, endpoint: str, handler: Callable):
        """Register a handler function for a specific endpoint."""
        self.handlers[endpoint] = handler
        logger.info(f"Registered handler for endpoint: {endpoint}")
        
    async def dispatch_message(self, message_body: Dict[str, Any]):
        """
        Dispatch the message to appropriate handler based on routing information.
        
        Args:
            message_body: Dictionary containing 'routing' and 'payload' keys
        
        Raises:
            QueueProcessorError: If message format is invalid or processing fails
        """
        try:
            if not isinstance(message_body, dict):
                raise QueueProcessorError(f"Invalid message format - expected dict, got {type(message_body)}")
            
            routing = message_body.get("routing")
            if not routing or not isinstance(routing, dict):
                raise QueueProcessorError(f"Invalid routing format - expected dict, got {type(routing)}")
            
            target_endpoint = routing.get("targetEndpoint")
            if not target_endpoint:
                raise QueueProcessorError("No target endpoint specified in message")
            
            payload = message_body.get("payload")
            if payload is None:
                raise QueueProcessorError("No payload found in message")
                
            # Try to get a specific handler, fall back to default if available
            handler = self.handlers.get(target_endpoint) or self.handlers.get("default")
            if not handler:
                raise QueueProcessorError(f"No handler registered for endpoint: {target_endpoint}")
            
            logger.info(f"Processing message for endpoint: {target_endpoint} with payload: {payload}")
            await handler(payload)
            logger.info(f"Successfully processed message for endpoint: {target_endpoint}")
                
        except QueueProcessorError as e:
            logger.error(str(e))
            raise
        except Exception as e:
            error_msg = f"Unexpected error processing message: {str(e)}"
            logger.error(error_msg)
            raise QueueProcessorError(error_msg) from e

class QueueProcessor:
    """Handles Azure Service Bus queue processing."""
    
    def __init__(self, connection_string: str, queue_name: str):
        self.connection_string = connection_string
        self.queue_name = queue_name
        self.dispatcher = MessageDispatcher()
        
    async def process_messages(self):
        """Process messages from the queue continuously."""
        try:
            async with ServiceBusClient.from_connection_string(self.connection_string) as client:
                async with client.get_queue_receiver(queue_name=self.queue_name) as receiver:
                    logger.info(f"Started listening to queue: {self.queue_name}")
                    while True:
                        try:
                            messages = await receiver.receive_messages(max_message_count=1, max_wait_time=5)
                            for msg in messages:
                                try:
                                    # Parse message body
                                    message_body = json.loads(str(msg))
                                    logger.info(f"Received message: {message_body}")
                                    
                                    if not isinstance(message_body, dict):
                                        logger.error(f"Invalid message format - expected dict, got {type(message_body)}")
                                        await receiver.dead_letter_message(msg, reason="Invalid message format")
                                        continue
                                        
                                    # Ensure required fields exist
                                    if 'routing' not in message_body or 'payload' not in message_body:
                                        logger.error("Message missing required fields (routing, payload)")
                                        await receiver.dead_letter_message(msg, reason="Missing required fields")
                                        continue
                                        
                                    # Dispatch message
                                    await self.dispatcher.dispatch_message(message_body)
                                    
                                    # Complete the message
                                    await receiver.complete_message(msg)
                                    
                                except Exception as e:
                                    logger.error(f"Error processing message: {str(e)}")
                                    await receiver.dead_letter_message(msg, reason=str(e))
                                    
                        except Exception as e:
                            logger.error(f"Error receiving messages: {str(e)}")
                            await asyncio.sleep(5)  # Wait before retrying
                            
        except Exception as e:
            logger.error(f"Error in queue processing: {str(e)}")
            raise

def create_queue_processor(connection_string: str, queue_name: str) -> QueueProcessor:
    """Create and initialize a queue processor."""
    return QueueProcessor(connection_string, queue_name)

async def initialize_queue_processor(processor: QueueProcessor):
    """Initialize the queue processor and start message processing."""
    asyncio.create_task(processor.process_messages())
    logger.info("Queue processor initialized and started")