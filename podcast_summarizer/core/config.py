"""Configuration settings for the podcast summarizer."""
from pydantic import HttpUrl
from pathlib import Path
from typing import Optional, Union
from pydantic_settings import BaseSettings

# Create temp directory for processing
Path("./temp").mkdir(exist_ok=True)

class Settings(BaseSettings):
    """Application settings."""

    # Whisper API settings
    WHISPER_API_KEY: str
    WHISPER_ENDPOINT: HttpUrl
    WHISPER_DEPLOYMENT_NAME: str
    WHISPER_API_VERSION: str = "2023-09-01-preview"

    # Local Whisper settings
    USE_LOCAL_WHISPER_FIRST: bool = True
    LOCAL_WHISPER_MODEL: str = "base.en"  # Options: tiny, base, small, medium, large

    # Azure Storage settings
    AZURE_STORAGE_CONNECTION_STRING: str
    AZURE_STORAGE_CONTAINER_NAME: str = "podcast-summarizer"

    # Database settings
    SUPABASE_URL: HttpUrl
    SUPABASE_KEY: str

    # Processing settings
    TEMP_DIR: Union[str, Path] = Path("./temp")
    MAX_CONCURRENT_DOWNLOADS: int = 3
    CACHE_TEMP_FILES: bool = False  # Whether to keep temp files after processing

    # LLM settings
    DEEPSEEK_API_KEY: str
    DEEPSEEK_ENDPOINT: HttpUrl
    DEEPSEEK_MODEL: str
    EMBEDDINGS_MODEL: str
    EMBEDDINGS_API_KEY: str
    EMBEDDINGS_ENDPOINT: HttpUrl
    DEEPSEEK_API_VERSION: str
    
    # Azure Service Bus settings
    SERVICE_BUS_CONNECTION_STRING: str
    SERVICE_BUS_QUEUE_NAME: str

    # Azure email settings
    AZURECONNECTIONSTRING: str
    SENDER_EMAIL: str
    RECEIVER_EMAIL: str

    #Pollingsettings
    QUEUE_POLLING_INTERVAL: int = 60 # Polling interval in seconds
    MAX_CPU_USAGE: float = 50  # Maximum CPU usage percentage for processing
    MAX_MEM_USAGE: float = 50  # Maximum memory usage percentage for processing
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

_settings = None

def get_settings():
    """Return initialized settings."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
