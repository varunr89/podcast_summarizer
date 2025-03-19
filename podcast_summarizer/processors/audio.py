"""
Audio processing utilities for the podcast summarizer.
"""
from pathlib import Path
from typing import List
import math

from ..core.logging_config import get_logger

logger = get_logger(__name__)

def split_audio_file(file_path: str, max_size_mb: float = 25.0) -> List[str]:
    """
    Split an audio file into smaller chunks if it exceeds the maximum size.
    
    Args:
        file_path: Path to the audio file
        max_size_mb: Maximum size in MB for each chunk
        
    Returns:
        List of paths to the split audio files
    """
    
    try:
        from pydub import AudioSegment
    except ImportError:
        logger.error("pydub package not found. Install with: pip install pydub")
        raise
    
    file_path = Path(file_path)
    
    # Check if file exceeds max size
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    if file_size_mb <= max_size_mb:
        logger.info(f"File {file_path.name} is under size limit ({file_size_mb:.2f}MB). No splitting needed.")
        return [str(file_path)]
    
    # Load audio file
    try:
        audio = AudioSegment.from_file(file_path)
    except Exception as e:
        logger.error(f"Error loading audio file {file_path}: {str(e)}")
        return [str(file_path)]  # Return original file if splitting fails
    
    # Target 60% of max size for safety
    target_size_mb = max_size_mb * 0.6
    
    # Estimate how many chunks we'll need
    num_chunks = math.ceil(file_size_mb / target_size_mb)
    
    # Estimate milliseconds per chunk based on duration
    total_duration_ms = len(audio)
    ms_per_chunk = int(total_duration_ms / num_chunks * 0.95)  # 5% safety margin
    
    logger.info(f"Splitting {file_path.name} ({file_size_mb:.2f}MB) into approximately {num_chunks} chunks")
    
    # Split audio and save chunks
    output_files = []
    start_ms = 0
    chunk_index = 1
    
    while start_ms < total_duration_ms:
        end_ms = min(start_ms + ms_per_chunk, total_duration_ms)
        
        # Extract chunk
        chunk = audio[start_ms:end_ms]
        
        # Create output filename
        chunk_file = file_path.parent / f"{file_path.stem}_chunk{chunk_index}{file_path.suffix}"
        
        # Export chunk
        chunk.export(chunk_file, format=file_path.suffix.replace('.', '') or 'mp3')
        
        # Verify size and adjust if needed for future chunks
        chunk_size_mb = chunk_file.stat().st_size / (1024 * 1024)
        if chunk_size_mb > max_size_mb:
            logger.warning(f"Chunk {chunk_index} slightly exceeds target size: {chunk_size_mb:.2f}MB > {max_size_mb:.2f}MB")
            # Reduce the estimate for future chunks
            adjustment_factor = max_size_mb / chunk_size_mb * 0.9
            ms_per_chunk = int(ms_per_chunk * adjustment_factor)
        
        output_files.append(str(chunk_file))
        logger.debug(f"Created chunk {chunk_index}: {chunk_file.name} ({chunk_size_mb:.2f}MB)")
        
        start_ms = end_ms
        chunk_index += 1
    
    logger.info(f"Successfully split {file_path.name} into {len(output_files)} files")
    return output_files

def convert_to_mp3(file_path: str, output_path: str = None) -> str:
    """
    Convert audio file to MP3 format if it's not already.
    
    Args:
        file_path: Path to the audio file
        output_path: Optional path for the output file
        
    Returns:
        Path to the MP3 file
    """
    try:
        from pydub import AudioSegment
    except ImportError:
        logger.error("pydub package not found. Install with: pip install pydub")
        raise
    
    file_path = Path(file_path)
    
    # If already an MP3, just return the path
    if file_path.suffix.lower() == '.mp3':
        return str(file_path)
    
    # Determine output path
    if not output_path:
        output_path = file_path.with_suffix('.mp3')
    else:
        output_path = Path(output_path)
    
    logger.info(f"Converting {file_path.name} to MP3")
    
    try:
        # Load audio and export as MP3
        audio = AudioSegment.from_file(file_path)
        audio.export(output_path, format='mp3')
        logger.info(f"Saved MP3 as {output_path}")
        return str(output_path)
    except Exception as e:
        logger.error(f"Error converting to MP3: {str(e)}")
        # Return original path if conversion fails
        return str(file_path)
