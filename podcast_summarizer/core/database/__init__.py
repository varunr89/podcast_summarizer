"""
Database client for podcast summarizer using Supabase.
"""
from .base import get_db
from .base import SupabaseManager
from .podcasts import PodcastManager
from .episodes import EpisodeManager
from .transcriptions import TranscriptionManager
from .summaries import SummaryManager

# Export the main functions and classes
__all__ = [
    'get_db',
    'SupabaseManager',
    'PodcastManager',
    'EpisodeManager',
    'TranscriptionManager',
    'SummaryManager'
]
