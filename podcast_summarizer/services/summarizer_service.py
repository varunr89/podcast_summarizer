"""
Main service for generating summaries from podcast transcriptions.
Integrates with the central summarization hub for efficient processing.
"""
from typing import Tuple, Dict, Any, List, Optional, Union
import re
import time

from ..core.logging_config import get_logger
from ..api.models import DetailLevel, SummarizationMethod
from ..processors.summarization import (
    summarize, 
    get_available_methods,
    SummaryResult,
    analyze_transcript_features
)

logger = get_logger(__name__)

def auto_select_method(transcription: str) -> str:
    """
    Automatically select the best summarization method based on transcript characteristics.
    
    Args:
        transcription: Full episode transcription text
        
    Returns:
        Selected summarization method name
    """
    logger.info("Auto-selecting summarization method based on transcript characteristics")
    
    # Use the refactored analyze_transcript_features function
    features = analyze_transcript_features(transcription)
    
    logger.debug(f"Transcript analysis: length={features['length']} chars, ~{features['word_count']} words, has_speakers={features['has_speaker_annotations']}")
    
    # Get available methods to choose from
    available_methods = get_available_methods()
    
    # Make a decision based on transcript characteristics
    if "spacy" in available_methods and features['has_speakers_annotations']:
        logger.info(f"Detected speaker annotations in transcript, using spaCy method")
        return "spacy"
    elif "llamaindex" in available_methods and features['length'] > 50000:
        logger.info(f"Detected long transcript ({features['length']} chars), using LlamaIndex method")
        return "llamaindex"
    elif "langchain" in available_methods:
        logger.info(f"Using LangChain method (default choice for {features['length']} char transcript)")
        return "langchain"
    else:
        logger.info(f"No preferred method available, defaulting to ensemble")
        return "ensemble"

def generate_episode_summary(
    transcription: str, 
    config: Any
) -> Tuple[str, Dict[str, Any], List[str]]:
    """
    Generate a summary from a podcast episode transcription using the specified method.
    
    Args:
        transcription: Full episode transcription text
        config: Configuration object with summarization parameters
        
    Returns:
        Tuple containing (summary text, key points dictionary, highlights list)
    """
    try:
        # Extract parameters from config object
        custom_prompt = config.custom_prompt
        chunk_size = config.chunk_size
        chunk_overlap = config.chunk_overlap
        detail_level = config.detail_level
        method = config.method
        temperature = config.temperature

        logger.info(f"Starting summary generation using method: {method}, detail level: {detail_level}")
        logger.debug(f"Params: chunk_size={chunk_size}, chunk_overlap={chunk_overlap}, temperature={temperature:.2f}")
        
        # Log transcript preview for debugging
        transcript_preview = transcription[:100].replace('\n', ' ').strip() + "..." if len(transcription) > 100 else transcription
        logger.debug(f"Processing transcript ({len(transcription)} chars): '{transcript_preview}'")
        
        if custom_prompt:
            custom_prompt_preview = custom_prompt[:100].replace('\n', ' ').strip() + "..." if len(custom_prompt) > 100 else custom_prompt
            logger.debug(f"Using custom prompt: '{custom_prompt_preview}'")
        
        # Validate detail level
        if detail_level not in [d.value for d in DetailLevel]:
            logger.warning(f"Invalid detail level: {detail_level}, defaulting to 'standard'")
            detail_level = DetailLevel.STANDARD
        
        # Auto-select method if specified
        selected_method = method
        if method == SummarizationMethod.AUTO:
            selected_method = auto_select_method(transcription)
            logger.info(f"Auto-selected method: {selected_method}")
        
        # Generate summary using our new centralized function
        start_time = time.time()
        
        # Call the centralized summarization function
        result = summarize(
            transcription=transcription,
            method=selected_method,
            custom_prompt=custom_prompt,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            detail_level=detail_level,
            temperature=temperature
        )
        
        elapsed_time = time.time() - start_time
        
        # Log the results
        logger.info(f"Summarization completed in {elapsed_time:.2f} seconds using {result.method} method")
        logger.debug(f"Generated summary length: {len(result.summary)} chars")
        logger.debug(f"Generated key points: {len(result.key_points)}")
        logger.debug(f"Generated highlights: {len(result.highlights)} items")
        
        # Preview the summary
        summary_preview = result.summary[:100].replace('\n', ' ').strip() + "..." if len(result.summary) > 100 else result.summary
        logger.debug(f"Summary preview: '{summary_preview}'")
        
        # Return in the original format expected by API clients
        return result.summary, {"points": result.key_points}, result.highlights
    
    except Exception as e:
        logger.error(f"Error generating summary with {getattr(config, 'method', 'unknown')} method: {str(e)}", exc_info=True)
        raise