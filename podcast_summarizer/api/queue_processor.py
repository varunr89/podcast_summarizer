"""Azure Service Bus queue processor and message dispatcher for the podcast summarizer API."""
import json
import logging
import asyncio
from typing import Dict, Any, Callable, Optional
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
import uuid
import time
import psutil

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
        message_id = message_body.get("id", str(uuid.uuid4()))
        start_time = time.time()
        logger.critical(f"STARTED processing message {message_id} at {start_time}")

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

            end_time = time.time()
            logger.critical(f"FINISHED processing message {message_id} at {end_time} (took {end_time - start_time:.2f} seconds)")        
        except QueueProcessorError as e:
            logger.error(str(e))
            raise
        except Exception as e:
            error_msg = f"Unexpected error processing message: {str(e)}"
            logger.error(error_msg)
            raise QueueProcessorError(error_msg) from e

class QueueProcessor:
    """Handles Azure Service Bus queue processing."""
    
    def __init__(self, connection_string: str, queue_name: str, max_cpu_percent: float = 50.0):
        self.connection_string = connection_string
        self.queue_name = queue_name
        self.dispatcher = MessageDispatcher()
        self.processing_lock = asyncio.Lock()  # This lock ensures sequential processing
        self.processing_task = None
        self._running = False
        self.max_cpu_percent = max_cpu_percent 

    async def is_system_ready(self) -> bool:
        """Check if the system is ready to process a new message."""
        # Get current CPU percentage (across all cores)
        cpu_percent = psutil.cpu_percent(interval=0.5)
        ready = cpu_percent < self.max_cpu_percent
        
        if not ready:
            logger.warning(f"System CPU usage {cpu_percent}% exceeds threshold {self.max_cpu_percent}%, delaying processing")
        else:
            logger.debug(f"System CPU usage {cpu_percent}% is below threshold {self.max_cpu_percent}%, ready to process")
            
        return ready

    async def process_messages(self):
        """Process messages from the queue continuously."""
        self._running = True
        try:
            async with ServiceBusClient.from_connection_string(self.connection_string) as client:
                async with client.get_queue_receiver(queue_name=self.queue_name, prefetch=1) as receiver:
                    logger.info(f"Started listening to queue: {self.queue_name}")
                    while self._running:
                        # Check system readiness before attempting to receive messages
                        if not await self.is_system_ready():
                            logger.info("System busy, waiting before polling for messages...")
                            await asyncio.sleep(120)  # Wait a bit longer when system is busy
                            continue

                        logger.info("Polling for messages on queue...")

                        try:
                            # Only receive 1 message at a time
                            logger.info(f"Attempting to receive messages from {self.queue_name}")
                            messages = await receiver.receive_messages(max_message_count=1, max_wait_time=5)
                            logger.info(f"Received {len(messages)} messages from queue")
                            
                            for msg in messages:
                                # Check system readiness again before processing the message
                                if not await self.is_system_ready():
                                    logger.warning("System became busy, releasing message back to queue")
                                    await receiver.abandon_message(msg)
                                     # Wait before trying again
                                    await asyncio.sleep(120)
                                    break
                                # Process one message at a time with the lock
                                async with self.processing_lock:
                                    try:
                                        # Parse message body
                                        message_body = json.loads(str(msg))
                                        logger.info(f"Processing message with routing: {message_body.get('routing', {}).get('targetEndpoint', 'unknown')}")
                                        
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
                                        logger.info("Message processed successfully")
                                        
                                    except Exception as e:
                                        logger.error(f"Error processing message: {str(e)}")
                                        await receiver.dead_letter_message(msg, reason=str(e))
                            
                            # Add a small delay between polling to reduce CPU usage
                            if not messages:
                                await asyncio.sleep(1)
                                
                        except asyncio.CancelledError:
                            logger.info("Message processing task cancelled")
                            raise
                        except Exception as e:
                            logger.error(f"Error receiving messages: {str(e)}")
                            await asyncio.sleep(5)  # Wait before retrying
                            
        except asyncio.CancelledError:
            logger.info("Queue processor shutting down")
        except Exception as e:
            logger.error(f"Error in queue processing: {str(e)}")
            raise
        finally:
            self._running = False
            
    async def shutdown(self):
        """Shut down the queue processor."""
        logger.info("Shutting down queue processor...")
        self._running = False
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
        logger.info("Queue processor shutdown complete")

# Update the create_queue_processor function to accept the new parameter
def create_queue_processor(connection_string: str, queue_name: str, max_cpu_percent: float = 50.0) -> QueueProcessor:
    """Create and initialize a queue processor."""
    return QueueProcessor(connection_string, queue_name, max_cpu_percent)

async def initialize_queue_processor(processor: QueueProcessor):
    """Initialize the queue processor and start message processing."""
    processor.processing_task = asyncio.create_task(processor.process_messages())
    logger.info("Queue processor initialized and started")
    return processor