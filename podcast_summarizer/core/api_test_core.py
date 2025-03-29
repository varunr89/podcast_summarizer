"""
Core functionality for testing the Podcast Summarizer API.
Refactored from api_test.py for reusability.
"""
import os
import time
from fastapi.testclient import TestClient
from dotenv import load_dotenv
from typing import List, Tuple, Dict, Optional, Any, Union

# Load environment variables
load_dotenv()

# Import the FastAPI app
from podcast_summarizer.api.main import app

# Try importing utility functions from the refactored codebase
try:
    from podcast_summarizer.utils.parsing import parse_episode_indices as api_parse_indices
    use_api_parser = True
except ImportError:
    use_api_parser = False

# Initialize the TestClient
client = TestClient(app)

def parse_episode_indices(indices_arg: Union[str, List[int]]) -> List[int]:
    """Parse episode indices from arguments, supporting both individual indices and ranges."""
    if use_api_parser:
        return api_parse_indices(indices_arg)
        
    if not indices_arg:
        return []
    
    result = []
    
    # Handle both comma-separated and space-separated values
    if isinstance(indices_arg, str):
        parts = indices_arg.replace(',', ' ').split()
    else:
        parts = indices_arg
        
    for part in parts:
        if isinstance(part, int):
            result.append(part)
        elif '-' in str(part):
            try:
                start, end = map(int, str(part).split('-'))
                if start <= end:
                    result.extend(range(start, end + 1))
                else:
                    print(f"Warning: Invalid range '{part}' (start > end), skipping")
            except ValueError:
                print(f"Warning: Could not parse range '{part}', skipping")
        else:
            try:
                result.append(int(part))
            except ValueError:
                print(f"Warning: '{part}' is not a valid episode index, skipping")
    
    return sorted(set(result))

def process_podcast(feed_url: Optional[str] = None,
                   limit_episodes: int = 1,
                   episode_indices: Optional[Union[str, List[int]]] = None,
                   split_size_mb: float = 25.0,
                   include_transcription: bool = True) -> Tuple[bool, Optional[str]]:
    """Process a podcast from RSS feed."""
    parsed_indices = parse_episode_indices(episode_indices) if episode_indices else None
    
    payload = {
        "feed_url": feed_url,
        "limit_episodes": limit_episodes if not parsed_indices else 0,
        "split_size_mb": split_size_mb,
        "include_transcription": include_transcription
    }
    
    if parsed_indices:
        payload["episode_indices"] = parsed_indices
    
    try:
        response = client.post("/process-podcast", json=payload)
        if response.status_code == 200:
            result = response.json()
            return True, result.get("job_id")
        return False, None
    except Exception as e:
        print(f"Exception during API call: {str(e)}")
        return False, None

def summarize_episode(
    episode_id: str,
    custom_prompt: Optional[str] = None,
    chunk_size: int = 4000,
    chunk_overlap: int = 200,
    method: str = "auto",
    detail_level: str = "standard",
    temperature: float = 0.5,
    user_id: str = "c4859aa4-50f7-43bd-9ff2-16efed5bf133"
) -> Tuple[bool, Optional[str]]:
    """Summarize a podcast episode."""
    payload = {
        "episode_id": episode_id,
        "custom_prompt": custom_prompt,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "method": method,
        "detail_level": detail_level,
        "temperature": temperature,
        "user_id": user_id
    }
    
    response = client.post("/summarize-episode", json=payload)
    
    if response.status_code == 200:
        result = response.json()
        return True, result.get('summary_id')
    return False, None

def get_episodes(transcribed_only: bool = True) -> List[str]:
    """Get list of available episodes."""
    try:
        endpoint = "/episodes/transcribed" if transcribed_only else "/episodes"
        response = client.get(endpoint)
        
        if response.status_code == 200:
            episodes = response.json()
            
            if transcribed_only and endpoint == "/episodes":
                filtered_episodes = [ep["id"] for ep in episodes if ep.get("transcription_status") == "completed"]
            else:
                filtered_episodes = [ep["id"] for ep in episodes]
            
            return filtered_episodes
        return []
    except Exception:
        return ["00000000-0000-0000-0000-000000000000"]

def upsert_podcast(feed_url: Optional[str] = None,
                  description: Optional[str] = None,
                  parser_type: str = "auto") -> Tuple[bool, Optional[str]]:
    """Upsert a podcast from an RSS feed."""
    payload = {
        "feed_url": feed_url,
        "parser_type": parser_type,
        "description": description or "Custom description for testing purposes"
    }
    
    response = client.post("/upsert-podcast", json=payload)
    
    if response.status_code == 200:
        result = response.json()
        return True, result.get("podcast_id")
    return False, None

def send_user_emails(user_id: str = "c4859aa4-50f7-43bd-9ff2-16efed5bf133") -> bool:
    """Send email summaries for a user's followed podcasts."""
    response = client.post(f"/send-user-emails/{user_id}")
    return response.status_code == 200

def send_episode_summary(user_id: str = "c4859aa4-50f7-43bd-9ff2-16efed5bf133",
                        episode_id: Optional[str] = None) -> bool:
    """Send a summary for a specific episode."""
    if not episode_id:
        return False
    
    response = client.post(f"/send-episode-summary/{user_id}/{episode_id}")
    return response.status_code == 200