"""
Functions for converting audio between different formats.
"""
from pathlib import Path

from ...core.logging_config import get_logger

logger = get_logger(__name__)

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