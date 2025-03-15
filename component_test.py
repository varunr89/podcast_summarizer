"""
Script to test each component of the Podcast Summarizer API with detailed logging.
"""
import os
import sys
import time
from fastapi.testclient import TestClient
from dotenv import load_dotenv
from pathlib import Path

# Add the parent directory to the sys.path to find the podcast_summarizer module
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Load environment variables
load_dotenv()

# Import the FastAPI app
from podcast_summarizer.api.main import app

# Initialize the TestClient
client = TestClient(app)

# Configure logging
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("component_test")

# Feed URL for testing
RSS_FEED_URL = "https://feeds.buzzsprout.com/1459246.rss"

def test_podcast_processing():
    """Test processing a podcast from RSS feed."""
    logger.info("=== Testing Podcast Processing API ===")
    
    # Request payload
    payload = {
        "feed_url": RSS_FEED_URL,
        "limit_episodes": 1,  # Just process one episode for the test
        "split_size_mb": 25.0,
        "include_transcription": True
    }
    
    # Make request to process podcast
    logger.info(f"Requesting processing of podcast: {RSS_FEED_URL}")
    response = client.post("/process-podcast", json=payload)
    
    if response.status_code == 200:
        result = response.json()
        job_id = result.get("job_id")
        logger.info(f"Processing started with job ID: {job_id}")
        logger.info("Status: %s", result.get("status"))
        
        return job_id
    else:
        logger.error(f"Error: {response.status_code}")
        logger.error(response.text)
        return None

def check_job_status(job_id):
    """Check the status of a processing job."""
    logger.info(f"Checking status for job: {job_id}")
    response = client.get(f"/job-status/{job_id}")
    
    if response.status_code == 200:
        result = response.json()
        status = result.get("status")
        logger.info(f"Job status: {status}")
        return status
    else:
        logger.error(f"Error checking job status: {response.status_code}")
        logger.error(response.text)
        return "error"

def test_episode_summarization(episode_id):
    """Test summarizing a podcast episode."""
    logger.info("\n=== Testing Episode Summarization API ===")
    
    # Request payload
    payload = {
        "episode_id": episode_id,
        "custom_prompt": """
        Create a comprehensive summary of this podcast episode, focusing on: 
        1. Main topics and key points
        2. Any technical concepts explained
        3. Key takeaways for the audience
        
        Format the summary with clear sections and bullet points for readability.
        """,
        "chunk_size": 4000,
        "chunk_overlap": 200
    }
    
    # Make request to summarize episode
    logger.info(f"Requesting summarization for episode: {episode_id}")
    response = client.post("/summarize-episode", json=payload)
    
    if response.status_code == 200:
        result = response.json()
        logger.info("Summarization completed!")
        logger.info(f"Episode ID: {result.get('episode_id')}")
        logger.info(f"Summary ID: {result.get('summary_id')}")
        logger.info(f"Status: {result.get('status')}")
        return True
    else:
        logger.error(f"Error: {response.status_code}")
        logger.error(response.text)
        return False


def get_available_episodes():
    """Get list of available transcribed episodes from Supabase directly."""
    # In a real scenario, you'd have an API endpoint for this
    # This is just a mock function that returns a sample episode ID
    
    # For testing purposes only - using a placeholder ID
    # In a real scenario, you would query Supabase for available episodes
    return ["00000000-0000-0000-0000-000000000000"]  # Replace with real ID when available


if __name__ == "__main__":
    print("=" * 50)
    print("PODCAST SUMMARIZER COMPONENT TEST")
    print("=" * 50)
    logger.info("Starting component test script...")
    
    try:
        # First, test podcast processing
        logger.info("Initiating podcast processing test...")
        job_id = test_podcast_processing()
        
        if job_id:
            logger.info("Podcast processing request successful!")
            
            # Check job status a few times (with a real endpoint)
            logger.info("\nChecking job status...")
            max_checks = 5
            for i in range(max_checks):
                logger.info(f"Status check {i+1} of {max_checks}")
                try:
                    status = check_job_status(job_id)
                    if status == "completed":
                        logger.info("Processing completed successfully!")
                        break
                    elif status == "failed":
                        logger.error("Processing failed!")
                        exit(1)
                    else:
                        logger.info(f"Processing still in progress ({status})")
                        if i < max_checks - 1:  # Don't sleep after the last check
                            sleep_time = 10  # seconds
                            logger.info(f"Waiting {sleep_time} seconds before checking again...")
                            time.sleep(sleep_time)
                except Exception as e:
                    logger.error(f"Error checking job status: {str(e)}")
                    break
        else:
            logger.error("Podcast processing test failed!")
            exit(1)
        
        # Try to get available episodes
        logger.info("\nGetting available episodes...")
        episode_ids = get_available_episodes()
        
        if episode_ids:
            # Test summarization with the first episode
            logger.info(f"Found episode ID: {episode_ids[0]}")
            test_episode_summarization(episode_ids[0])
        else:
            logger.info("No episodes available for summarization.")
            logger.info("This is expected if you just started processing your first podcast.")
            logger.info("Try running the script again after processing completes.")
            
        print("\nComponent test completed. Check the logs above for results.")
        
    except Exception as e:
        logger.error(f"An error occurred during testing: {str(e)}")
        raise
