"""
Functions for cleaning and preprocessing audio files.
"""
from pathlib import Path
import tempfile
import subprocess
import os
import shutil
from typing import Optional, Tuple, List

from ...core.logging_config import get_logger

logger = get_logger(__name__)

def clean_audio_for_transcription(file_path: str) -> str:
    """
    Clean an audio file by removing silence, music, and other non-speech elements to reduce transcription costs.
    
    Processing steps:
    1. Convert to mono if stereo
    2. Normalize audio levels
    3. Remove leading/trailing silence
    4. Trim music intro/outro (>10s of continuous non-speech)
    5. Collapse long pauses (>0.5s) to shorter pauses (0.2s)
    6. Downsample to 16 kHz
    7. Speed up speech segments by 1.25x
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        Path to the cleaned audio file
    """
    # Validate input path
    if not file_path:
        logger.error("No file path provided for audio cleaning")
        return ""
    
    file_path = Path(file_path)
    
    # Check if file exists
    if not file_path.exists():
        logger.error(f"Audio file not found: {file_path}")
        return str(file_path)  # Return original path
    
    logger.info(f"Cleaning audio file for transcription: {file_path}")
    
    # Create a temporary directory for processing files
    temp_dir = tempfile.mkdtemp()
    cleaned_path = file_path.parent / f"{file_path.stem}_cleaned.mp3"
    
    try:
        # Process audio with unified approach
        result_path = process_audio(file_path, cleaned_path, temp_dir)
        
        # Verify the result
        if result_path and Path(result_path).exists() and Path(result_path).stat().st_size > 0:
            return result_path
        else:
            logger.warning("Audio cleaning failed to produce valid output, returning original")
            return str(file_path)
    
    except Exception as e:
        logger.error(f"Error cleaning audio file: {str(e)}", exc_info=True)
        return str(file_path)  # Return original file if cleaning fails
    
    finally:
        # Clean up temp directory
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as cleanup_error:
            logger.warning(f"Failed to clean up temp files: {str(cleanup_error)}")

def process_audio(input_path: Path, output_path: Path, temp_dir: str) -> Optional[str]:
    """
    Process audio using FFmpeg with pydub fallback for each step.
    
    Args:
        input_path: Path to the input audio file
        output_path: Path where the cleaned audio will be saved
        temp_dir: Temporary directory for intermediate files
    
    Returns:
        Path to the processed audio file or None if processing failed
    """
    # First try all-in-one FFmpeg approach (most efficient)
    if try_full_ffmpeg_processing(input_path, output_path):
        return calculate_and_log_duration_change(input_path, output_path)
    
    logger.info("Full FFmpeg processing failed, trying step-by-step approach")
    
    # Initialize for step-by-step processing
    current_file = input_path
    temp_counter = 0
    
    # Step 1: Convert to mono and normalize
    temp_counter += 1
    step_output = Path(temp_dir) / f"step{temp_counter}.wav"
    success, result_file = process_step(
        current_file, 
        step_output, 
        "Convert to mono and normalize", 
        ffmpeg_cmd=[
            "ffmpeg", "-y", "-i", "{input}", 
            "-ac", "1", "-af", "dynaudnorm=f=100:g=15:n=0:p=0.95", 
            "{output}"
        ],
        pydub_function=convert_and_normalize_pydub
    )
    
    if not success:
        logger.error("Failed to process audio in initial step")
        return None
    
    current_file = result_file
    
    # Step 2: Remove leading/trailing silence
    temp_counter += 1
    step_output = Path(temp_dir) / f"step{temp_counter}.wav"
    success, result_file = process_step(
        current_file,
        step_output,
        "Remove leading/trailing silence",
        ffmpeg_cmd=[
            "ffmpeg", "-y", "-i", "{input}",
            "-af", "silenceremove=start_periods=1:start_duration=0.1:start_threshold=-30dB:detection=peak,"
                   "silenceremove=stop_periods=-1:stop_duration=0.5:stop_threshold=-30dB:detection=peak",
            "{output}"
        ],
        pydub_function=remove_silence_pydub
    )
    
    if success:
        current_file = result_file
    
    # Step 3: Remove long non-speech sections
    temp_counter += 1
    step_output = Path(temp_dir) / f"step{temp_counter}.wav"
    success, result_file = process_step(
        current_file,
        step_output,
        "Remove long non-speech sections",
        ffmpeg_cmd=[
            "ffmpeg", "-y", "-i", "{input}",
            "-af", "silenceremove=stop_periods=-1:stop_duration=10:stop_threshold=-25dB:start_periods=1:start_silence=1.5:start_threshold=-25dB",
            "{output}"
        ],
        pydub_function=remove_long_silence_pydub
    )
    
    if success:
        current_file = result_file
    
    # Step 4: Speed up audio
    temp_counter += 1
    step_output = Path(temp_dir) / f"step{temp_counter}.wav"
    success, result_file = process_step(
        current_file,
        step_output,
        "Speed up audio",
        ffmpeg_cmd=[
            "ffmpeg", "-y", "-i", "{input}",
            "-af", "atempo=1.25",
            "{output}"
        ],
        pydub_function=speed_up_pydub
    )
    
    if success:
        current_file = result_file
    
    # Final step: Downsample to 16kHz and export to mp3
    try:
        cmd = [
            "ffmpeg", "-y", "-i", str(current_file),
            "-ar", "16000", str(output_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        
        if output_path.exists() and output_path.stat().st_size > 0:
            return calculate_and_log_duration_change(input_path, output_path)
    except Exception as e:
        logger.warning(f"Final export with FFmpeg failed: {str(e)}")
        try:
            # Fallback to pydub for final export
            from pydub import AudioSegment
            audio = AudioSegment.from_file(current_file)
            audio = audio.set_frame_rate(16000)
            audio.export(output_path, format="mp3")
            
            if output_path.exists() and output_path.stat().st_size > 0:
                return calculate_and_log_duration_change(input_path, output_path)
        except Exception as e:
            logger.error(f"Failed to export final audio: {str(e)}")
    
    return None

def try_full_ffmpeg_processing(input_path: Path, output_path: Path) -> bool:
    """Try to process the entire audio with a single FFmpeg command"""
    try:
        # Check if FFmpeg is available
        subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True)
        
        # Create filter chain for audio processing
        filter_complex = [
            # Convert to mono and normalize audio
            "aformat=channel_layouts=mono",
            "dynaudnorm=f=100:g=15:n=0:p=0.95",
            
            # Remove silence, keeping only sections with audio above -30dB for at least 0.1s
            # and skipping silence longer than 0.5s
            "silenceremove=start_periods=1:start_duration=0.1:start_threshold=-30dB:detection=peak",
            "silenceremove=stop_periods=-1:stop_duration=0.5:stop_threshold=-30dB:detection=peak",
            
            # Remove intro/outro music or long non-speech sections (>10s)
            "silenceremove=stop_periods=-1:stop_duration=10:stop_threshold=-25dB:start_periods=1:start_silence=1.5:start_threshold=-25dB",
            
            # Speed up the audio by 1.25x without changing pitch
            "atempo=1.25"
        ]
        
        # Build the FFmpeg command
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-af", ",".join(filter_complex),
            "-ar", "16000",  # Resample to 16 kHz
            str(output_path)
        ]
        
        # Run FFmpeg
        logger.debug(f"Running FFmpeg command: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True, capture_output=True)
        
        # Verify the output file exists and has content
        return output_path.exists() and output_path.stat().st_size > 0
    
    except Exception as e:
        logger.warning(f"Full FFmpeg processing failed: {str(e)}")
        return False

def process_step(input_file: Path, output_file: Path, step_name: str, 
                ffmpeg_cmd: List[str], pydub_function) -> Tuple[bool, Path]:
    """
    Process an audio step, trying FFmpeg first then falling back to pydub.
    
    Args:
        input_file: Current audio file
        output_file: Where to save the processed output
        step_name: Name of the processing step for logging
        ffmpeg_cmd: FFmpeg command with {input} and {output} placeholders
        pydub_function: Function to call if FFmpeg fails
    
    Returns:
        Tuple of (success boolean, result file path)
    """
    logger.debug(f"Processing step: {step_name}")
    
    # Try with FFmpeg first
    try:
        # Replace placeholders in command
        cmd = [arg.format(input=input_file, output=output_file) if isinstance(arg, str) else arg for arg in ffmpeg_cmd]
        subprocess.run(cmd, check=True, capture_output=True)
        
        if output_file.exists() and output_file.stat().st_size > 0:
            logger.debug(f"FFmpeg {step_name} successful")
            return True, output_file
    except Exception as e:
        logger.warning(f"FFmpeg {step_name} failed: {str(e)}")
    
    # Fall back to pydub
    logger.debug(f"Falling back to pydub for {step_name}")
    try:
        success = pydub_function(input_file, output_file)
        if success and output_file.exists() and output_file.stat().st_size > 0:
            logger.debug(f"Pydub {step_name} successful")
            return True, output_file
        else:
            logger.warning(f"Pydub {step_name} failed to produce valid output")
            return False, input_file
    except Exception as e:
        logger.warning(f"Pydub {step_name} failed with error: {str(e)}")
        return False, input_file

def calculate_and_log_duration_change(input_path: Path, output_path: Path) -> str:
    """Calculate and log the duration change between input and output files"""
    try:
        get_duration_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", 
                           "-of", "default=noprint_wrappers=1:nokey=1", str(output_path)]
        output_duration = float(subprocess.check_output(get_duration_cmd).decode('utf-8').strip())
        
        get_orig_duration_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", 
                               "-of", "default=noprint_wrappers=1:nokey=1", str(input_path)]
        orig_duration = float(subprocess.check_output(get_orig_duration_cmd).decode('utf-8').strip())
        
        reduction_percent = ((orig_duration - output_duration) / orig_duration) * 100
        logger.info(f"Duration reduced from {orig_duration:.2f}s to {output_duration:.2f}s ({reduction_percent:.1f}% reduction)")
    except Exception as e:
        logger.warning(f"Error calculating duration metrics: {str(e)}")
    
    return str(output_path)

# Pydub fallback implementations
def convert_and_normalize_pydub(input_file: Path, output_file: Path) -> bool:
    """Convert to mono and normalize using pydub"""
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(input_file)
        
        # Convert to mono
        if audio.channels > 1:
            audio = audio.set_channels(1)
        
        # Normalize audio levels
        target_dBFS = -20.0
        change_in_dBFS = target_dBFS - audio.dBFS
        audio = audio.apply_gain(change_in_dBFS)
        
        audio.export(output_file, format="wav")
        return True
    except Exception as e:
        logger.error(f"Pydub convert and normalize failed: {str(e)}")
        return False

def remove_silence_pydub(input_file: Path, output_file: Path) -> bool:
    """Remove leading/trailing silence using pydub"""
    try:
        from pydub import AudioSegment
        from pydub.silence import detect_nonsilent
        
        audio = AudioSegment.from_file(input_file)
        silence_thresh = audio.dBFS - 14
        non_silent_ranges = detect_nonsilent(
            audio, 
            min_silence_len=300,  # 300ms
            silence_thresh=silence_thresh
        )
        
        if not non_silent_ranges:
            logger.warning("No speech detected in audio file")
            return False
        
        # Trim to first and last non-silent sections
        start_trim = non_silent_ranges[0][0]
        end_trim = non_silent_ranges[-1][1]
        audio = audio[start_trim:end_trim]
        
        # Collapse pauses
        silent_ranges = detect_nonsilent(
            audio, 
            min_silence_len=500,  # 500ms
            silence_thresh=silence_thresh,
            seek_step=1
        )
        
        if silent_ranges:
            processed_audio = AudioSegment.empty()
            last_end = 0
            
            for start, end in silent_ranges:
                # Add the audio segment before this silence
                processed_audio += audio[last_end:start]
                
                # Add a shorter silence (200ms) instead of the full pause
                processed_audio += AudioSegment.silent(duration=200)
                
                last_end = end
            
            # Add the final segment after the last silence
            processed_audio += audio[last_end:]
            audio = processed_audio
        
        audio.export(output_file, format="wav")
        return True
    except Exception as e:
        logger.error(f"Pydub silence removal failed: {str(e)}")
        return False

def remove_long_silence_pydub(input_file: Path, output_file: Path) -> bool:
    """Remove long non-speech sections using pydub"""
    try:
        from pydub import AudioSegment
        from pydub.silence import detect_silence
        
        audio = AudioSegment.from_file(input_file)
        silence_thresh = audio.dBFS - 14
        
        # Detect long silences that might be music sections
        long_silences = detect_silence(
            audio, 
            min_silence_len=10000,  # 10 seconds
            silence_thresh=silence_thresh - 5  # Use lower threshold for music
        )
        
        # If we found long silences, process them
        if long_silences:
            logger.debug(f"Found {len(long_silences)} potential music segments")
            # Remove these sections (keeping a bit of context)
            processed_audio = AudioSegment.empty()
            last_end = 0
            
            for i, (start, end) in enumerate(long_silences):
                # Keep audio up to 1.5 seconds before the long silence
                section_start = max(0, last_end)
                section_end = max(0, start - 1500) if start > 1500 else 0
                
                if section_end > section_start:
                    processed_audio += audio[section_start:section_end]
                
                # Skip the silence entirely
                last_end = end
            
            # Add the final part after the last long silence
            if last_end < len(audio):
                processed_audio += audio[last_end:]
            
            # Only replace if we have content
            if len(processed_audio) > 0:
                audio = processed_audio
        
        audio.export(output_file, format="wav")
        return True
    except Exception as e:
        logger.error(f"Pydub long silence removal failed: {str(e)}")
        return False

def speed_up_pydub(input_file: Path, output_file: Path) -> bool:
    """Speed up audio using pydub"""
    try:
        from pydub import AudioSegment
        
        audio = AudioSegment.from_file(input_file)
        
        # Attempt to use pydub's speedup effect
        try:
            from pydub.effects import speedup
            audio = speedup(audio, 1.25, 150)
        except Exception as e:
            logger.warning(f"Pydub speedup effect failed: {str(e)}")
            # We'll just continue with the unaltered audio in this case
        
        audio.export(output_file, format="wav")
        return True
    except Exception as e:
        logger.error(f"Pydub speed up failed: {str(e)}")
        return False
