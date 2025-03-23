"""
Audio processing utilities for the podcast summarizer.
"""
from pathlib import Path
from typing import List, Tuple
import math
import os
import tempfile
import subprocess
from typing import Optional

# Re-export all functions from their respective modules
from .splitting import split_audio_file
from .conversion import convert_to_mp3
from .cleaning import clean_audio_for_transcription, process_audio, try_full_ffmpeg_processing, process_step
from .detection import detect_music_segments

# Export all functions as if they were defined in this module
__all__ = [
    'split_audio_file',
    'convert_to_mp3',
    'clean_audio_for_transcription',
    'process_audio',
    'try_full_ffmpeg_processing',
    'process_step',
    'detect_music_segments'
]
