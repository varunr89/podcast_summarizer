"""Frontend API for the podcast summarizer service."""
from flask import Flask, request, jsonify
from azure.servicebus import ServiceBusClient, ServiceBusMessage
import os
import json
import uuid
from datetime import datetime
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

if not connection_string:
    raise ValueError("SERVICE_BUS_CONNECTION_STRING environment variable is not set")
if not queue_name:
    raise ValueError("SERVICE_BUS_QUEUE_NAME environment variable is not set")

app.logger.info("Azure Service Bus configuration loaded successfully")

def send_message_to_queue(message_body):
    """
    Sends a message to Azure Service Bus Queue.
    Args:
        message_body: A dictionary containing the request envelope.
    """
    servicebus_client = ServiceBusClient.from_connection_string(connection_string)
    with servicebus_client:
        sender = servicebus_client.get_queue_sender(queue_name=queue_name)
        message = ServiceBusMessage(json.dumps(message_body))
        with sender:
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
def forward_request():
    """
    Generic forwarding endpoint that validates requests based on target_path
    and forwards them to Azure Service Bus Queue.
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
            elif target_path.startswith("/send-user-emails/"):
                validated_request = UserEmailRequest(**request_data)
                target_endpoint = "send-user-emails"
            elif target_path.startswith("/send-episode-summary/"):
                validated_request = EpisodeEmailRequest(**request_data)
                target_endpoint = "send-episode-summary"
            else:
                return jsonify({"error": f"Invalid target_path: {target_path}"}), 400

            # Create and send envelope
            validated_data = validated_request.model_dump(exclude_unset=True)
            envelope = create_envelope(validated_data, target_endpoint)
            send_message_to_queue(envelope)

            return jsonify({
                "message": "Request accepted for processing",
                "correlationId": envelope["metadata"]["correlationId"],
                "status": "queued",
                "timestamp": envelope["metadata"]["timestamp"]
            }), 202

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