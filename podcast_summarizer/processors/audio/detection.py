"""
Functions for detecting specific segments in audio files.
"""
from typing import List, Tuple
from pathlib import Path

from ...core.logging_config import get_logger

logger = get_logger(__name__)

def detect_music_segments(audio_path: str, threshold: float = 0.6, min_duration: float = 10.0) -> List[Tuple[int, int]]:
    """
    Detect music segments in an audio file using spectral properties.
    This is a simple implementation that can be enhanced with librosa for better results.
    
    Args:
        audio_path: Path to the audio file
        threshold: Threshold for music detection (0.0-1.0)
        min_duration: Minimum duration in seconds to consider a segment as music
        
    Returns:
        List of tuples with start and end times (in ms) of music segments
    """
    # Validate input path
    if not audio_path:
        logger.error("No file path provided for music detection")
        return []
    
    audio_path_obj = Path(audio_path)
    if not audio_path_obj.exists():
        logger.error(f"Audio file not found for music detection: {audio_path}")
        return []
    
    try:
        import numpy as np
        from pydub import AudioSegment
    except ImportError:
        logger.error("Required packages not found. Install with: pip install pydub numpy")
        return []
    
    try:
        # Try to import librosa for better music detection
        import librosa
        has_librosa = True
    except ImportError:
        has_librosa = False
        logger.warning("librosa not found, falling back to basic detection. Install with: pip install librosa")
    
    try:
        if has_librosa:
            # Advanced detection with librosa
            y, sr = librosa.load(audio_path)
            
            # Extract features
            spec_cent = librosa.feature.spectral_centroid(y=y, sr=sr)
            spec_bw = librosa.feature.spectral_bandwidth(y=y, sr=sr)
            
            # Music tends to have higher spectral centroid and bandwidth
            spec_cent_norm = (spec_cent - np.min(spec_cent)) / (np.max(spec_cent) - np.min(spec_cent))
            spec_bw_norm = (spec_bw - np.min(spec_bw)) / (np.max(spec_bw) - np.min(spec_bw))
            
            # Combine features
            music_likelihood = (spec_cent_norm + spec_bw_norm) / 2
            
            # Convert to time segments
            frame_length = len(y) / len(music_likelihood[0])
            music_segments = []
            
            # Identify segments with high music likelihood
            is_music = False
            start_frame = 0
            
            for i, likelihood in enumerate(music_likelihood[0]):
                if likelihood > threshold and not is_music:
                    is_music = True
                    start_frame = i
                elif likelihood <= threshold and is_music:
                    is_music = False
                    duration = (i - start_frame) * frame_length / sr
                    if duration >= min_duration:
                        music_segments.append((
                            int(start_frame * frame_length / sr * 1000),  # Start time in ms
                            int(i * frame_length / sr * 1000)             # End time in ms
                        ))
            
            # Handle if file ends with music
            if is_music:
                duration = (len(music_likelihood[0]) - start_frame) * frame_length / sr
                if duration >= min_duration:
                    music_segments.append((
                        int(start_frame * frame_length / sr * 1000),
                        int(len(y) / sr * 1000)
                    ))
            
            return music_segments
        else:
            # Basic detection with pydub and numpy
            # This is much less accurate but doesn't require librosa
            audio = AudioSegment.from_file(audio_path)
            samples = np.array(audio.get_array_of_samples())
            
            # Simple approach: check for constant energy levels typical of music
            # This won't be very accurate but can detect some intro/outro music
            
            # Convert mono to stereo if needed
            if audio.channels == 1:
                samples = np.array([samples, samples]).T
            
            # Calculate energy in windows
            window_size = int(audio.frame_rate * 1.0)  # 1 second window
            windows = []
            
            for i in range(0, len(samples), window_size):
                if i + window_size < len(samples):
                    windows.append(samples[i:i+window_size])
            
            # Calculate variance in each window
            variances = [np.var(window) for window in windows]
            normalized_var = [(v - min(variances)) / (max(variances) - min(variances) + 1e-10) for v in variances]
            
            # Music tends to have more consistent variance compared to speech
            consistency = []
            for i in range(1, len(normalized_var)):
                consistency.append(abs(normalized_var[i] - normalized_var[i-1]))
            
            # Identify segments of consistent variance (potential music)
            music_segments = []
            is_music = False
            start_window = 0
            
            for i, cons in enumerate(consistency):
                if cons < 0.2 and not is_music:  # Low variance change suggests consistent audio (music)
                    is_music = True
                    start_window = i
                elif (cons >= 0.2 or i == len(consistency) - 1) and is_music:
                    is_music = False
                    duration = (i - start_window) * (window_size / audio.frame_rate)
                    if duration >= min_duration:
                        music_segments.append((
                            int(start_window * window_size * 1000 / audio.frame_rate),  # Start time in ms
                            int(i * window_size * 1000 / audio.frame_rate)             # End time in ms
                        ))
            
            return music_segments
            
    except Exception as e:
        logger.error(f"Error detecting music segments: {str(e)}", exc_info=True)
        return []
