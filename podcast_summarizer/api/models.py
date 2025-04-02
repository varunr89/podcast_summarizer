"""
Pydantic models for the API requests and responses.
"""
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Literal
from enum import Enum

class DetailLevel(str, Enum):
    """Detail level options for summaries"""
    BRIEF = "brief"
    STANDARD = "standard"
    DETAILED = "detailed"

class SummarizationMethod(str, Enum):
    """Summarization method options"""
    LANGCHAIN = "langchain"
    LLAMAINDEX = "llamaindex"
    SPACY = "spacy"
    ENSEMBLE = "ensemble"
    AUTO = "auto"

class ParserType(str, Enum):
    """Parser type options for podcast feeds"""
    RSS = "rss"
    CRAWLER = "crawler"
    AUTO = "auto"

class PodcastFeedRequest(BaseModel):
    """Request model for podcast processing"""
    feed_url: str
    split_size_mb: int = 25
    podcast_id: Optional[str] = None
    limit_episodes: Optional[int] = None
    episode_indices: Optional[List[int]] = None
    start_episode: Optional[int] = None
    episode_count: Optional[int] = None
    keep_audio_files: bool = False
    parser_type: ParserType = ParserType.AUTO

class EpisodeSummaryRequest(BaseModel):
    """Request model for episode summary generation"""
    episode_id: str
    user_id: Optional[str] = "c4859aa4-50f7-43bd-9ff2-16efed5bf133"
    custom_prompt: Optional[str] = None
    chunk_size: int = Field(default=4000, ge=500, le=8000)
    chunk_overlap: int = Field(default=500, ge=0, le=1000)
    detail_level: DetailLevel = DetailLevel.STANDARD
    method: SummarizationMethod = SummarizationMethod.AUTO
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)

class PodcastUpsertRequest(BaseModel):
    """Request model for podcast upsert operation"""
    feed_url: str
    description: Optional[str] = None
    parser_type: ParserType = ParserType.AUTO

class UserEmailRequest(BaseModel):
    """Request model for sending user emails"""
    user_id: str

class EpisodeEmailRequest(BaseModel):
    """Request model for sending episode summary emails"""
    user_id: str
    episode_id: str
