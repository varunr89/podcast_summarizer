"""
Example script demonstrating usage of the Podcast Summarizer API.
"""
__test__ = False
import os
import time
import argparse
import json
from fastapi.testclient import TestClient
from dotenv import load_dotenv

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

def parse_episode_indices(indices_arg):
    """
    Parse episode indices from command line arguments, supporting both individual indices and ranges.
    Examples: 
    - "1,3,5" -> [1,3,5]
    - "1-5" -> [1,2,3,4,5]
    - "1,3-5,7" -> [1,3,4,5,7]
    """
    # Use the API's utility function if available
    if use_api_parser:
        return api_parse_indices(indices_arg)
        
    if not indices_arg:
        return None
    
    result = []
    
    # Handle both comma-separated and space-separated values
    if isinstance(indices_arg, str):
        parts = indices_arg.replace(',', ' ').split()
    else:
        # Handle when argparse provides a list directly
        parts = indices_arg
        
    for part in parts:
        if isinstance(part, int):
            # Direct integer from argparse
            result.append(part)
        elif '-' in str(part):
            # Handle ranges like "5-10"
            try:
                start, end = map(int, str(part).split('-'))
                if start <= end:  # Validate range is logical
                    result.extend(range(start, end + 1))
                else:
                    print(f"Warning: Invalid range '{part}' (start > end), skipping")
            except ValueError:
                print(f"Warning: Could not parse range '{part}', skipping")
        else:
            # Handle individual numbers
            try:
                result.append(int(part))
            except ValueError:
                print(f"Warning: '{part}' is not a valid episode index, skipping")
    
    return sorted(set(result))  # Remove duplicates and sort

def test_podcast_processing(feed_url=None, limit_episodes=1, episode_indices=None, split_size_mb=25.0, include_transcription=True):
    """Test processing a podcast from RSS feed."""
    print("=== Testing Podcast Processing API ===")
       
    # Parse episode indices if provided
    if episode_indices:
        parsed_indices = parse_episode_indices(episode_indices)
        print(f"Parsed episode indices: {parsed_indices}")
    else:
        parsed_indices = None
    
    # Request payload
    payload = {
        "feed_url": feed_url,
        "limit_episodes": limit_episodes if not parsed_indices else 0,  # Don't use limit if specific indices provided
        "split_size_mb": split_size_mb,
        "include_transcription": include_transcription
    }
    
    # Add episode_indices if provided
    if parsed_indices:
        payload["episode_indices"] = parsed_indices
        print(f"Requesting specific episodes: {parsed_indices}")
    
    # Make request to process podcast
    print(f"Requesting processing of podcast: {feed_url}")
    
    try:
        response = client.post("/process-podcast", json=payload)
        
        if response.status_code == 200:
            result = response.json()
            job_id = result.get("job_id")
            print(f"Processing started with job ID: {job_id}")
            print("Status:", result.get("status"))
            
            return True, job_id
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
            return False, None
    except Exception as e:
        print(f"Exception during API call: {str(e)}")
        return False, None


def test_episode_summarization(
    episode_id, 
    custom_prompt=None, 
    chunk_size=4000, 
    chunk_overlap=200,
    method="auto",
    detail_level="standard",
    temperature=0.5,
    user_id="c4859aa4-50f7-43bd-9ff2-16efed5bf133"  # Default user_id for testing
):
    """Test summarizing a podcast episode."""
    print("\n=== Testing Episode Summarization API ===")
    
    # Request payload
    payload = {
        "episode_id": episode_id,
        "custom_prompt": custom_prompt,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "method": method,
        "detail_level": detail_level,
        "temperature": temperature,
        "user_id": user_id # Always include user_id in the payload
    }
    
    # Make request to summarize episode
    print(f"Requesting summarization for episode: {episode_id}")
    print(f"Method: {method}, Detail level: {detail_level}, User ID: {user_id}")
    response = client.post("/summarize-episode", json=payload)
    
    if response.status_code == 200:
        result = response.json()
        print("Summarization completed!")
        print(f"Episode ID: {result.get('episode_id')}")
        print(f"Summary ID: {result.get('summary_id')}")
        print(f"Status: {result.get('status')}")
        print(f"Method used: {result.get('method', method)}")
        return True, result.get('summary_id')
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return False, None


def get_available_episodes(transcribed_only=True):
    """Get list of available episodes from Supabase."""
    print("\n=== Getting Available Episodes ===")
    
    try:
        # Check for specialized endpoint based on filter criteria
        endpoint = "/episodes/transcribed" if transcribed_only else "/episodes"
        
        response = client.get(endpoint)
        
        if response.status_code == 200:
            episodes = response.json()
            
            # If using /episodes endpoint, we may still need to filter
            if transcribed_only and endpoint == "/episodes":
                filtered_episodes = [ep["id"] for ep in episodes if ep.get("transcription_status") == "completed"]
            else:
                filtered_episodes = [ep["id"] for ep in episodes]
            
            if filtered_episodes:
                print(f"Found {len(filtered_episodes)} episodes")
                return filtered_episodes
            else:
                print("No matching episodes found")
                return []
        else:
            print(f"Error fetching episodes: {response.status_code}")
            print(response.text)
            return []
    except Exception as e:
        print(f"Exception when fetching episodes: {e}")
        print("Using placeholder episode ID for testing")
        return ["00000000-0000-0000-0000-000000000000"]


def test_upsert_podcast(feed_url=None, description=None, parser_type="auto", verbose=False):
    """Test upserting a podcast from an RSS feed."""
    print("\n=== Testing Podcast Upsert API ===")
      
    # Request payload for initial creation
    payload = {
        "feed_url": feed_url,
        "parser_type": parser_type
    }
    
    if description is not None:
        payload["description"] = description
    else:
        payload["description"] = "Custom description for testing purposes"
    
    print(f"Creating new podcast from feed: {feed_url}")
    print(f"Using parser type: {parser_type}")
    if verbose:
        print(f"Request payload: {json.dumps(payload, indent=2)}")
    
    # Request to upsert a podcast
    response = client.post("/upsert-podcast", json=payload)
    
    if verbose and response.status_code != 200:
        print("\n--- Detailed Error Information ---")
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        try:
            error_json = response.json()
            print(f"Error JSON: {json.dumps(error_json, indent=2)}")
        except:
            print(f"Raw Error Response: {response.text}")
        print("--------------------------------")
    
    if response.status_code == 200:
        result = response.json()
        podcast_id = result.get("podcast_id")
        print(f"Successfully upserted podcast with ID: {podcast_id}")
        print(f"Title: {result.get('title')}")
        print(f"Episode count: {result.get('episode_count')}")
        print(f"Status: {result.get('status')}")
        return True, podcast_id
    else:
        print(f"Error upserting podcast: {response.status_code}")
        print(response.text)
        return False, None


def test_send_user_emails(user_id="c4859aa4-50f7-43bd-9ff2-16efed5bf133"):
    """Test sending email summaries for a user's followed podcasts."""
    print("\n=== Testing Send User Emails API ===")
    
    # Request payload
    payload = {
        "user_id": user_id
    }
    
    print(f"Requesting email summaries for user: {user_id}")
    response = client.post("/send-user-emails", json=payload)
    
    if response.status_code == 200:
        result = response.json()
        print("Email sending completed!")
        print(f"Status: {result.get('status')}")
        print(f"Message: {result.get('message')}")
        print(f"Episodes processed: {result.get('episodes_processed')}")
        return True
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return False

def test_send_episode_summary(user_id="c4859aa4-50f7-43bd-9ff2-16efed5bf133", episode_id=None):
    """Test sending a summary for a specific episode."""
    print("\n=== Testing Send Episode Summary API ===")
    
    if not episode_id:
        print("No episode ID provided")
        return False
    
    # Request payload
    payload = {
        "user_id": user_id,
        "episode_id": episode_id
    }
    
    print(f"Requesting summary email for user: {user_id}, episode: {episode_id}")
    response = client.post("/send-episode-summary", json=payload)
    
    if response.status_code == 200:
        result = response.json()
        print("Email sending completed!")
        print(f"Status: {result.get('status')}")
        print(f"Message: {result.get('message')}")
        print(f"Episode title: {result.get('episode_title')}")
        return True
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return False

def run_tests(args):
    """Run the specified tests based on command line arguments."""
    results = {}
    
    # Test podcast upserting
    if args.test_upsert:
        success, podcast_id = test_upsert_podcast(
            args.feed_url,
            args.description,
            args.parser_type,
            args.verbose
        )
        results['upsert'] = {'success': success, 'podcast_id': podcast_id}
    
    # Test podcast processing
    if args.test_process:
        success, job_id = test_podcast_processing(
            args.feed_url,
            args.limit_episodes,
            args.episode_indices,  # Pass the episode indices string or list
            args.split_size_mb,
            args.include_transcription
        )
        results['process'] = {'success': success, 'job_id': job_id}
    
    # Wait for processing if requested
    if args.wait and args.wait > 0:
        print(f"\nWaiting {args.wait} seconds for processing...")
        time.sleep(args.wait)
    
    # Get available episodes
    if args.test_episodes or args.test_summarize:
        episode_ids = get_available_episodes(args.transcribed_only)
        results['episodes'] = episode_ids
        
        # Test summarization if requested and episodes are available
        if args.test_summarize and episode_ids:
            episode_to_summarize = episode_ids[0]
            if args.episode_id:
                # Use specified episode ID if provided
                episode_to_summarize = args.episode_id
                
            success, summary_id = test_episode_summarization(
                episode_to_summarize,
                args.custom_prompt,
                args.chunk_size,
                args.chunk_overlap,
                args.method,
                args.detail_level,
                args.temperature,
                args.user_id
            )
            results['summarize'] = {'success': success, 'summary_id': summary_id}
    
    # Test email functionality if requested
    if args.test_email:
        success = test_send_user_emails(args.user_id)
        results['email'] = {'success': success}
    
    if args.test_episode_email and args.episode_id:
        success = test_send_episode_summary(args.user_id, args.episode_id)
        results['episode_email'] = {'success': success}
    
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test the Podcast Summarizer API")
    
    # General options
    parser.add_argument('--feed-url', type=str, help='RSS feed URL to process')
    parser.add_argument('--wait', type=int, default=5, help='Seconds to wait between processing and querying episodes')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output with detailed error information')
    
    # Test selection options
    parser.add_argument('--test-all', action='store_true', help='Run all tests')
    parser.add_argument('--test-upsert', action='store_true', help='Test podcast upsert API')
    parser.add_argument('--test-process', action='store_true', help='Test podcast processing API')
    parser.add_argument('--test-episodes', action='store_true', help='Test getting episodes')
    parser.add_argument('--test-summarize', action='store_true', help='Test episode summarization')
    parser.add_argument('--test-email', action='store_true', help='Test sending email summaries')
    parser.add_argument('--test-episode-email', action='store_true', help='Test sending specific episode summary')
    
    # Upsert options
    parser.add_argument('--description', type=str, help='Custom description for podcast')
    parser.add_argument('--parser-type', type=str, default='auto', 
                        choices=['auto', 'rss', 'crawler'], 
                        help='Parser type to use (auto, rss, crawler)')
    parser.add_argument('--test-update', action='store_true', 
                        help='Test updating an existing podcast (may cause duplicates if upsert does not work correctly)')
    
    # Processing options
    parser.add_argument('--limit-episodes', type=int, default=1, help='Limit number of episodes to process')
    parser.add_argument('--split-size-mb', type=float, default=25.0, help='Split size in MB')
    parser.add_argument('--include-transcription', type=bool, default=True, help='Whether to include transcription')
    parser.add_argument('--episode-indices', type=str, help='Specific episode indices to process (1-based). Can use ranges like "25-50" or individual indices like "1,5,10"')
    
    # Episode options
    parser.add_argument('--transcribed-only', action='store_true', help='Only get transcribed episodes')
    parser.add_argument('--episode-id', type=str, help='Specific episode ID to summarize')
    
    # Summarization options
    parser.add_argument('--custom-prompt', type=str, help='Custom prompt for summarization')
    parser.add_argument('--chunk-size', type=int, default=4000, help='Chunk size for summarization')
    parser.add_argument('--chunk-overlap', type=int, default=200, help='Chunk overlap for summarization')
    parser.add_argument('--method', type=str, default='auto', help='Summarization method (auto, langchain, llamaindex, spacy, ensemble)')
    parser.add_argument('--detail-level', type=str, default='standard', help='Detail level (brief, standard, detailed)')
    parser.add_argument('--temperature', type=float, default=0.5, help='Temperature parameter for LLM')
    parser.add_argument('--user-id', type=str, help='Optional user ID for tracking summaries')
    
    args = parser.parse_args()
    
    # If --test-all is specified, enable all tests
    if args.test_all:
        args.test_upsert = True
        args.test_process = True
        args.test_episodes = True
        args.test_summarize = True
        args.test_email = True
        args.test_episode_email = True
    
    # If no tests specified, default to running all tests
    if not (args.test_upsert or args.test_process or args.test_episodes or
            args.test_summarize or args.test_email or args.test_episode_email):
        args.test_upsert = True
        args.test_process = True
        args.test_episodes = True
        args.test_summarize = True
        args.test_email = True
        args.test_episode_email = True
    
    # Run the tests
    results = run_tests(args)
    
    print("\n=== Test Results Summary ===")
    for test, result in results.items():
        if isinstance(result, dict) and 'success' in result:
            print(f"{test}: {'Success' if result['success'] else 'Failed'}")
        elif isinstance(result, list):
            print(f"{test}: Found {len(result)} items")
