"""
Parameter validation and conversion helper for GUI components.
Ensures parameters meet the requirements defined in models.py.
"""
from typing import Any, Dict, List, Union, Optional
from enum import Enum


class ValidationError(Exception):
    """Custom exception for parameter validation errors."""
    pass


def convert_to_int(value: str, param_name: str) -> int:
    """Convert string to integer, with appropriate error handling."""
    try:
        # First try converting to float in case it's a string like "25.0"
        float_val = float(value)
        return int(float_val)
    except (ValueError, TypeError):
        raise ValidationError(f"Parameter '{param_name}' must be a valid number")


def convert_to_float(value: str, param_name: str, min_val: float, max_val: float) -> float:
    """Convert string to float within specified bounds."""
    try:
        float_val = float(value)
        if not min_val <= float_val <= max_val:
            raise ValidationError(
                f"Parameter '{param_name}' must be between {min_val} and {max_val}")
        return float_val
    except (ValueError, TypeError):
        raise ValidationError(f"Parameter '{param_name}' must be a valid number")


def parse_episode_indices(value: str) -> List[int]:
    """Convert episode indices string to list of integers."""
    if not value:
        return []
        
    try:
        # If it's a single number, wrap it in a list
        if value.strip().isdigit():
            return [int(value)]
            
        # Split by comma and convert each part
        indices = []
        parts = value.split(',')
        for part in parts:
            # Basic support for ranges (e.g., "1-3")
            if '-' in part:
                start, end = map(int, part.split('-'))
                indices.extend(range(start, end + 1))
            else:
                indices.append(int(part))
        return indices
    except (ValueError, TypeError):
        raise ValidationError(
            "Episode indices must be numbers separated by commas (e.g., '1,2,3' or '1-3')")


def validate_chunk_size(value: int) -> int:
    """Validate chunk size is within bounds (500-8000)."""
    if not 500 <= value <= 8000:
        raise ValidationError("Chunk size must be between 500 and 8000")
    return value


def validate_chunk_overlap(value: int) -> int:
    """Validate chunk overlap is within bounds (0-1000)."""
    if not 0 <= value <= 1000:
        raise ValidationError("Chunk overlap must be between 0 and 1000")
    return value


def validate_temperature(value: float) -> float:
    """Validate temperature is within bounds (0.0-1.0)."""
    if not 0.0 <= value <= 1.0:
        raise ValidationError("Temperature must be between 0.0 and 1.0")
    return value


def convert_and_validate_param(param_name: str, value: str, test_type: str) -> Any:
    """Convert and validate a parameter based on its name and test type."""
    # Skip empty values
    if not value:
        return None
        
    # Convert boolean strings
    if value.lower() in ('true', 'false'):
        return value.lower() == 'true'
        
    try:
        # Handle specific parameter types
        if param_name == 'split_size_mb':
            return convert_to_int(value, param_name)
            
        elif param_name == 'episode_indices':
            return parse_episode_indices(value)
            
        elif param_name == 'chunk_size':
            size = convert_to_int(value, param_name)
            return validate_chunk_size(size)
            
        elif param_name == 'chunk_overlap':
            overlap = convert_to_int(value, param_name)
            return validate_chunk_overlap(overlap)
            
        elif param_name == 'temperature':
            return validate_temperature(convert_to_float(value, param_name, 0.0, 1.0))
            
        elif param_name == 'limit_episodes':
            return convert_to_int(value, param_name)
            
        # Default string parameters
        return value
            
    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(f"Error processing parameter '{param_name}': {str(e)}")


def validate_payload(payload: Dict[str, Any], test_type: str) -> None:
    """Validate the complete payload based on test type."""
    if test_type == "process":
        if not payload.get("feed_url"):
            raise ValidationError("Feed URL is required for process operations")
            
    elif test_type == "summarize":
        if not payload.get("episode_id"):
            raise ValidationError("Episode ID is required for summarize operations")
        if not payload.get("user_id"):
            raise ValidationError("User ID is required for summarize operations")
            
    elif test_type == "upsert":
        if not payload.get("feed_url"):
            raise ValidationError("Feed URL is required for upsert operations")