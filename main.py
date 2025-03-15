"""
Entry point for the Podcast Summarizer API server.
"""
import os
import sys
import uvicorn
from dotenv import load_dotenv
from pathlib import Path

# Add parent directory to path so we can import the package
sys.path.insert(0, str(Path(__file__).parent))

# Import the FastAPI app
from podcast_summarizer.api.main import app

# Load environment variables
load_dotenv()

def check_environment():
    """Verify that necessary environment variables are set."""
    required_vars = [
        "WHISPER_API_KEY",
        "WHISPER_ENDPOINT",
        "WHISPER_DEPLOYMENT_NAME",
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_ENDPOINT",
        "DEEPSEEK_MODEL",
    ]
    
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
        print("Please set these variables in your .env file or environment.")
        return False
    
    return True

if __name__ == "__main__":
    if check_environment():
        print("Starting Podcast Summarizer API server...")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        print("Cannot start server due to missing configuration.")
        sys.exit(1)
