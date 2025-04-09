"""
Command processing helper for GUI components.
Builds and validates service bus requests.
"""
import json
import requests
from typing import Dict, Any, Tuple, Optional, Union, List
import copy
from .param_validator import convert_and_validate_param, validate_payload, ValidationError

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

def build_request_payload(test_type: str, params: Dict[str, str], extra_params: str = "") -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """Build the JSON payload for the service bus request."""
    try:
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
            
            # Normalize the path by removing trailing slashes
            target_path = target_path.rstrip('/')
        
        payload = {"target_path": target_path}
        
        # Convert and validate each parameter
        for name, value in params.items():
            # Skip user-id and episode-id for email routes as they're in the path
            if test_type in ["email", "episode_email"] and name in ["user_id", "episode_id"]:
                continue
                
            # Convert parameter name format
            api_name = name.replace("-", "_")
            
            # Convert and validate the parameter 
            converted_value = convert_and_validate_param(api_name, value, test_type)
            if converted_value is not None:
                payload[api_name] = converted_value
        
        # For process test type, ensure include_transcription and split_size_mb are always provided
        if test_type == "process":
            if "include_transcription" not in payload:
                payload["include_transcription"] = True
            if "split_size_mb" not in payload:
                payload["split_size_mb"] = 25
            
            # Handle multiple episode indices
            if "episode_indices" in payload and isinstance(payload["episode_indices"], list):
                indices = payload["episode_indices"]
                if len(indices) > 1:
                    payloads = []
                    for index in indices:
                        new_payload = copy.deepcopy(payload)
                        new_payload["episode_indices"] = [index]
                        # Validate each individual payload
                        validate_payload(new_payload, test_type)
                        payloads.append(new_payload)
                    return payloads
        
        # Add any extra parameters
        if extra_params:
            try:
                extra_dict = json.loads(extra_params)
                payload.update(extra_dict)
            except json.JSONDecodeError:
                raise ValidationError("Error parsing extra parameters JSON")
        
        # Validate the complete payload
        validate_payload(payload, test_type)
        
        return payload
    
    except ValidationError as e:
        raise ValidationError(f"Validation error: {str(e)}")
    except Exception as e:
        raise ValidationError(f"Error building payload: {str(e)}")

def send_request(payload: Dict[str, Any]) -> Tuple[Optional[int], str]:
    """Send request to the service bus."""
    try:
        resp = requests.post(
            SERVICE_BUS_URL,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        return resp.status_code, resp.text
    except Exception as e:
        return None, str(e)