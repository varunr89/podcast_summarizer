"""Frontend API for the podcast summarizer service."""
from flask import Flask, request, jsonify
from azure.servicebus import ServiceBusClient, ServiceBusMessage
import os
import json
import uuid
from datetime import datetime, timedelta
import time
import psutil
import asyncio
from azure.mgmt.monitor import MonitorManagementClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from pydantic import ValidationError

from models import (
    PodcastFeedRequest,
    PodcastUpsertRequest,
    EpisodeSummaryRequest,
    UserEmailRequest,
    EpisodeEmailRequest
)

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Azure Service Bus connection details
connection_string = os.getenv('SERVICE_BUS_CONNECTION_STRING')
queue_name = os.getenv('SERVICE_BUS_QUEUE_NAME')
subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
resource_group = os.getenv('AZURE_RESOURCE_GROUP')
container_app_name = os.getenv('AZURE_APP_SERVICE_NAME')

# Validate required environment variables
required_vars = {
    'SERVICE_BUS_CONNECTION_STRING': connection_string,
    'SERVICE_BUS_QUEUE_NAME': queue_name,
    'AZURE_SUBSCRIPTION_ID': subscription_id,
    'AZURE_RESOURCE_GROUP': resource_group,
    'AZURE_APP_SERVICE_NAME': container_app_name
}

for var_name, var_value in required_vars.items():
    if not var_value:
        raise ValueError(f"{var_name} environment variable is not set")

app.logger.info("Azure Service Bus configuration loaded successfully")

# Initialize Azure Monitor client for metrics
credential = DefaultAzureCredential()
monitor_client = MonitorManagementClient(credential, subscription_id)

async def get_system_metrics():
    """Get system metrics including CPU usage and container count."""
    try:
        # Get CPU metrics for the app service
        metrics_data = monitor_client.metrics.list(
    resource_uri=(
        f'/subscriptions/{subscription_id}/resourceGroups/{resource_group}/'
        f'providers/Microsoft.App/containerApps/{container_app_name}'
    ),
    timespan=f"{(datetime.utcnow() - timedelta(minutes=5)).isoformat()}/{datetime.utcnow().isoformat()}",
    interval='PT1M',
    metricnames='CpuPercentage,MemoryPercentage,Requests,Replicas',
    aggregation='Average'
)

        # Extract CPU percentage and instance count
        for metric in metrics_data.value:
            if metric.name.value == 'CpuPercentage' and metric.timeseries:
                cpu_percent = metric.timeseries[0].data[-1].average or 0
            elif metric.name.value == 'Replicas' and metric.timeseries:
                instance_count = metric.timeseries[0].data[-1].average or 1

        return {
            'cpu_percent': cpu_percent,
            'instance_count': instance_count
        }
    except Exception as e:
        app.logger.error(f"Error getting system metrics: {str(e)}")
        # Fallback to psutil for local development
        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'instance_count': 1
        }

async def calculate_delay(metrics, attempt=0):
    """Calculate delay based on system metrics and attempt count."""
    cpu_percent = metrics['cpu_percent']
    instance_count = metrics['instance_count']
    
    if cpu_percent <= 50:
        return 0
    
    # Base delay increases with CPU usage and decreases with instance count
    base_delay = 60  # 1 minute base delay
    
    # Adjust base delay based on CPU usage
    if cpu_percent > 90:
        cpu_factor = 2.0
    elif cpu_percent > 75:
        cpu_factor = 1.5
    else:
        cpu_factor = 1.0
    
    # Adjust for number of instances
    instance_factor = 1.0 / instance_count
    
    # Calculate delay with exponential backoff
    delay = base_delay * cpu_factor * instance_factor * (2 ** attempt)
    
    # Cap maximum delay at 30 minutes
    return min(delay, 1800)

def send_message_to_queue(message_body, delay_seconds=None):
    """
    Sends a message to Azure Service Bus Queue, optionally scheduling it for later processing.
    Args:
        message_body: A dictionary containing the request envelope.
        delay_seconds: Optional delay in seconds before the message becomes available.
    """
    servicebus_client = ServiceBusClient.from_connection_string(connection_string)
    with servicebus_client:
        sender = servicebus_client.get_queue_sender(queue_name=queue_name)
        message = ServiceBusMessage(json.dumps(message_body))
        
        with sender:
            if delay_seconds:
                # Calculate scheduled time
                scheduled_time = datetime.utcnow() + timedelta(seconds=delay_seconds)
                scheduled_time_epoch = int(time.mktime(scheduled_time.timetuple()))
                
                # Schedule the message
                sender.schedule_messages(message, scheduled_time_epoch)
                app.logger.info(
                    f"Scheduled message for queue | correlationId: {message_body['metadata']['correlationId']} | "
                    f"targetEndpoint: {message_body['routing']['targetEndpoint']} | "
                    f"timestamp: {message_body['metadata']['timestamp']} | "
                    f"scheduled_time: {scheduled_time.isoformat()}"
                )
            else:
                # Send immediately
                sender.send_messages(message)
                app.logger.info(
                    f"Message forwarded to queue | correlationId: {message_body['metadata']['correlationId']} | "
                    f"targetEndpoint: {message_body['routing']['targetEndpoint']} | "
                    f"timestamp: {message_body['metadata']['timestamp']}"
                )

def create_envelope(payload: dict, target_endpoint: str):
    """Creates a message envelope with metadata and routing."""
    correlation_id = str(uuid.uuid4())
    return {
        "payload": payload,
        "metadata": {
            "correlationId": correlation_id,
            "timestamp": datetime.now().isoformat(),
            "sourceEndpoint": request.path
        },
        "routing": {
            "targetEndpoint": target_endpoint
        }
    }

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({"status": "healthy"}), 200

@app.route('/api/forward', methods=['POST'])
async def forward_request():
    """
    Generic forwarding endpoint that validates requests based on target_path
    and forwards them to Azure Service Bus Queue with adaptive delay.
    """
    try:
        request_data = request.json
        if not request_data:
            return jsonify({"error": "Request body must contain valid JSON"}), 400

        # Validate based on target_path
        target_path = request_data.get('target_path')
        if not target_path:
            return jsonify({"error": "target_path is required"}), 400

        try:
            # Select validation model based on target_path
            if target_path == "/process-podcast":
                validated_request = PodcastFeedRequest(**request_data)
                target_endpoint = "process-podcast"
            elif target_path == "/upsert-podcast":
                validated_request = PodcastUpsertRequest(**request_data)
                target_endpoint = "upsert-podcast"
            elif target_path == "/summarize-episode":
                validated_request = EpisodeSummaryRequest(**request_data)
                target_endpoint = "summarize-episode"
            elif target_path.startswith("/send-user-emails"):
                validated_request = UserEmailRequest(**request_data)
                target_endpoint = "send-user-emails"
            elif target_path.startswith("/send-episode-summary"):
                validated_request = EpisodeEmailRequest(**request_data)
                target_endpoint = "send-episode-summary"
            else:
                return jsonify({"error": f"Invalid target_path: {target_path}"}), 400

            # Get system metrics and calculate delay with exponential backoff
            attempt = 0
            max_attempts = 5  # Maximum number of delay attempts
            metrics = None
            delay_seconds = None
            
            while attempt < max_attempts:
                # Get current system metrics
                metrics = await get_system_metrics()
                delay_seconds = await calculate_delay(metrics, attempt)
                
                if delay_seconds == 0:  # System is ready to process
                    break
                    
                app.logger.info(
                    f"System busy (CPU: {metrics['cpu_percent']}%, Instances: {metrics['instance_count']}). "
                    f"Attempt {attempt + 1}/{max_attempts}, waiting {delay_seconds} seconds..."
                )
                
                # Wait before checking again
                await asyncio.sleep(min(60, delay_seconds))  # Check at most every minute
                attempt += 1
            
            # Create and send envelope
            validated_data = validated_request.model_dump(exclude_unset=True)
            envelope = create_envelope(validated_data, target_endpoint)
            scheduled_time = send_message_to_queue(envelope, delay_seconds if delay_seconds else None)

            response = {
                "message": "Request accepted for processing",
                "correlationId": envelope["metadata"]["correlationId"],
                "status": "queued",
                "timestamp": envelope["metadata"]["timestamp"],
                "system_metrics": {
                    "cpu_percent": metrics["cpu_percent"] if metrics else None,
                    "instance_count": metrics["instance_count"] if metrics else None,
                    "attempt": attempt
                }
            }
            
            if delay_seconds:
                response["scheduled_time"] = scheduled_time.isoformat()
                response["delay_seconds"] = delay_seconds
                response["retry_count"] = attempt

            return jsonify(response), 202

        except ValidationError as ve:
            app.logger.error(f"Validation error for {target_path}: {str(ve)}")
            return jsonify({
                "error": "Validation error",
                "details": ve.errors()
            }), 422

    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON in request body"}), 400
    except Exception as e:
        app.logger.error(f"Error processing request: {str(e)}")
        return jsonify({"error": "Failed to process request"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)