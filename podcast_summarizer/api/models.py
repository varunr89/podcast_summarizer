from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, List, Dict, Any, Union

class PodcastFeedRequest(BaseModel):
    """Request model for processing a podcast feed."""
    feed_url: HttpUrl
    limit_episodes: int = 1
    episode_indices: Optional[List[int]] = None  # This can now accept a parsed list of indices
    split_size_mb: float = 25.0
    include_transcription: bool = True
    podcast_id: Optional[str] = None
    keep_audio_files: bool = False  # Flag to control if audio files should be kept after transcription
    start_episode: Optional[int] = None  # NEW: Starting episode index
    episode_count: Optional[int] = None  # NEW: Number of episodes to process from start

class EpisodeSummaryRequest(BaseModel):
    episode_id: str
    custom_prompt: Optional[str] = None
    chunk_size: int = 4000
    chunk_overlap: int = 200

class PodcastUpsertRequest(BaseModel):
    feed_url: str
    description: str = None

class EpisodeSummaryRequest(BaseModel):
    """Enhanced request model for episode summarization"""
    episode_id: str
    user_id: str
    custom_prompt: Optional[str] = None
    chunk_size: int = 4000
    chunk_overlap: int = 500
    detail_level: DetailLevel = DetailLevel.STANDARD
    method: SummarizationMethod = SummarizationMethod.AUTO
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
