"""
Business logic for command generation and request processing in Podcast Summarizer Testing.
"""
import json
import requests

# Service Bus endpoint
SERVICE_BUS_URL = "https://podcast-frontend-api.whitedesert-b2508737.westus.azurecontainerapps.io/api/forward"

# Mapping test types to their API endpoints
TARGET_PATH_MAP = {
    "upsert": "/upsert-podcast",
    "process": "/process-podcast",
    "summarize": "/summarize-episode",
    "email": "/send-user-emails",
    "episode_email": "/send-episode-summary"
}

def build_request_payload(test_type: str, params: dict, extra_params: str = "") -> dict:
    """Build the JSON payload for the service bus request."""
    payload = {}
    
    # Set the target path based on test type
    target_path = TARGET_PATH_MAP.get(test_type)
    
    # For email endpoints, include IDs in the path
    if test_type in ["email", "episode_email"]:
        uid = params.get("user_id", "").strip()
        if test_type == "email":
            target_path = f"/send-user-emails/{uid}"
        else:  # episode_email
            eid = params.get("episode_id", "").strip()
            target_path = f"/send-episode-summary/{uid}/{eid}"
    
    payload["target_path"] = target_path
    
    # Add parameters to payload
    for key, value in params.items():
        # Skip user-id and episode-id for email routes as they're in the path
        if test_type in ["email", "episode_email"] and key in ["user_id", "episode_id"]:
            continue
            
        # Try to convert to appropriate type
        try:
            value = int(value)
        except ValueError:
            try:
                value = float(value)
            except ValueError:
                # Convert string "true"/"false" to boolean
                if isinstance(value, str):
                    if value.lower() == "true":
                        value = True
                    elif value.lower() == "false":
                        value = False
        
        payload[key] = value
    
    # For process test type, ensure include_transcription and split_size_mb are always provided
    if test_type == "process":
        if "include_transcription" not in payload:
            payload["include_transcription"] = True
        if "split_size_mb" not in payload:
            payload["split_size_mb"] = 25.0
    
    # Add any extra parameters
    if extra_params:
        try:
            extra_dict = json.loads(extra_params)
            payload.update(extra_dict)
        except json.JSONDecodeError:
            pass
    
    return payload

def send_request(payload: dict) -> tuple:
    """Send request to the service bus endpoint."""
    try:
        resp = requests.post(
            SERVICE_BUS_URL, 
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        return resp.status_code, resp.text
    except Exception as e:
        return None, str(e)

def build_test_command(test_type: str, params: list, extra_params: str = "", env: str = "local_source") -> str:
    """Build the complete test command based on environment and parameters."""
    # Build the api_test.py command part
    cmd = [f"--test-{test_type}"]
    
    # Add parameters that are enabled and have values
    for param, value in params:
        cmd.append(f"--{param} {value}")
        
    # Add any extra parameters
    if extra_params:
        cmd.append(extra_params)
        
    api_cmd = " ".join(cmd)
    
    if env == "local_source":
        # For local source, just prepend python command
        final_cmd = f"python src/api_test.py {api_cmd}"
    else:
        # For Docker, wrap the command appropriately
        final_cmd = (
            'docker run -it --rm --env-file "src/.env" podcast_summarizer '
            'bash -c "uvicorn src.podcast_summarizer.api.main:app '
            '--host 0.0.0.0 --port 80 & sleep 3 && '
            f'python src/api_test.py {api_cmd}"'
        )
    
    return final_cmd