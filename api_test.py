"""
Example script demonstrating usage of the Podcast Summarizer API.
"""
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
                result.extend(range(start, end + 1))  # +1 because range is exclusive at the end
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
    
    # Use default if no feed URL provided
    if feed_url is None:
        feed_url = "https://feeds.buzzsprout.com/1459246.rss"
    
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
    response = client.post("/process-podcast", json=payload)
    
    if response.status_code == 200:
        result = response.json()
        job_id = result.get("job_id")
        print(f"Processing started with job ID: {job_id}")
        print("Status:", result.get("status"))
        
        # In a real application, you might poll a /job-status endpoint to check progress
        # For this example, we'll just wait a bit
        print("Waiting for processing (this may take several minutes for real podcasts)...")
        print("In a real application, you would poll for status or use webhooks.")
        
        return True, job_id
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return False, None


def test_episode_summarization(episode_id, custom_prompt=None, chunk_size=4000, chunk_overlap=200):
    """Test summarizing a podcast episode."""
    print("\n=== Testing Episode Summarization API ===")
    
    # Use default prompt if none provided
    if custom_prompt is None:
        custom_prompt = """
        Create a comprehensive summary of this podcast episode, focusing on: 
        1. Main topics and key points
        2. Any technical concepts explained
        3. Key takeaways for the audience
        
        Format the summary with clear sections and bullet points for readability.
        """
    
    # Request payload
    payload = {
        "episode_id": episode_id,
        "custom_prompt": custom_prompt,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap
    }
    
    # Make request to summarize episode
    print(f"Requesting summarization for episode: {episode_id}")
    response = client.post("/summarize-episode", json=payload)
    
    if response.status_code == 200:
        result = response.json()
        print("Summarization completed!")
        print(f"Episode ID: {result.get('episode_id')}")
        print(f"Summary ID: {result.get('summary_id')}")
        print(f"Status: {result.get('status')}")
        return True, result.get('summary_id')
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return False, None


def get_available_episodes(transcribed_only=True):
    """Get list of available episodes from Supabase."""
    print("\n=== Getting Available Episodes ===")
    
    try:
        response = client.get("/episodes")
        
        if response.status_code == 200:
            episodes = response.json()
            
            if transcribed_only:
                # Filter for episodes that have been transcribed
                filtered_episodes = [ep["id"] for ep in episodes if ep.get("transcription_status") == "completed"]
            else:
                # Return all episodes
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
        # Fallback to placeholder for testing
        print("Using placeholder episode ID for testing")
        return ["00000000-0000-0000-0000-000000000000"]  # Replace with real ID when available


def test_upsert_podcast(feed_url=None, description=None, verbose=False):
    """Test upserting a podcast from an RSS feed, first creating then updating it."""
    print("\n=== Testing Podcast Upsert API ===")
    
    # Use default if no feed URL provided
    if feed_url is None:
        feed_url = "https://feeds.buzzsprout.com/1459246.rss"
    
    # Request payload for initial creation
    payload = {
        "feed_url": feed_url
    }
    
    if description is not None:
        payload["description"] = description
    else:
        payload["description"] = "Custom description for testing purposes"
    
    print(f"Creating new podcast from feed: {feed_url}")
    if verbose:
        print(f"Request payload: {json.dumps(payload, indent=2)}")
    
    # First request - should create a new podcast
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
        print(f"Successfully created podcast with ID: {podcast_id}")
        print(f"Title: {result.get('title')}")
        print(f"Episode count: {result.get('episode_count')}")
        print(f"Status: {result.get('status')}")
        
        # Second request - should update the existing podcast
        print("\nUpdating the same podcast (checking for new episodes)")
        update_payload = {
            "feed_url": feed_url
        }
        
        update_response = client.post("/upsert-podcast", json=update_payload)
        
        if update_response.status_code == 200:
            update_result = update_response.json()
            print(f"Update successful for podcast ID: {update_result.get('podcast_id')}")
            print(f"New episodes added: {update_result.get('new_episodes_added')}")
            print(f"Total episodes: {update_result.get('total_episodes')}")
            print(f"Status: {update_result.get('status')}")
            return True, podcast_id
        else:
            print(f"Error updating podcast: {update_response.status_code}")
            print(update_response.text)
            return False, None
    else:
        print(f"Error creating podcast: {response.status_code}")
        print(response.text)
        return False, None


def run_tests(args):
    """Run the specified tests based on command line arguments."""
    results = {}
    
    # Test podcast upserting
    if args.test_upsert:
        success, podcast_id = test_upsert_podcast(args.feed_url, args.description, args.verbose)
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
                args.chunk_overlap
            )
            results['summarize'] = {'success': success, 'summary_id': summary_id}
    
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
    
    # Upsert options
    parser.add_argument('--description', type=str, help='Custom description for podcast')
    
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
    
    args = parser.parse_args()
    
    # If --test-all is specified, enable all tests
    if args.test_all:
        args.test_upsert = True
        args.test_process = True
        args.test_episodes = True
        args.test_summarize = True
    
    # If no tests specified, default to running all tests
    if not (args.test_upsert or args.test_process or args.test_episodes or args.test_summarize):
        args.test_upsert = True
        args.test_process = True
        args.test_episodes = True
        args.test_summarize = True
    
    # Run the tests
    results = run_tests(args)
    
    print("\n=== Test Results Summary ===")
    for test, result in results.items():
        if isinstance(result, dict) and 'success' in result:
            print(f"{test}: {'Success' if result['success'] else 'Failed'}")
        elif isinstance(result, list):
            print(f"{test}: Found {len(result)} items")
