"""
Main service for generating summaries from podcast transcriptions.
Integrates multiple summarization methods.
"""
from typing import Tuple, Dict, Any, List, Optional
from enum import Enum

from ..core.logging_config import get_logger
from ..processors.langchain_summarizer import summarize_with_langchain, LLAMAINDEX_AVAILABLE
from ..processors.ensemble_summarizer import summarize_with_ensemble
from ..processors.spacy_transformer_summarizer import summarize_with_spacy, SPACY_TRANSFORMERS_AVAILABLE

try:
    from ..processors.llamaindex_summarizer import summarize_with_llamaindex
except ImportError:
    pass

logger = get_logger(__name__)

class SummarizationMethod(str, Enum):
    """Summarization method options"""
    LANGCHAIN = "langchain"
    LLAMAINDEX = "llamaindex"
    SPACY = "spacy"
    ENSEMBLE = "ensemble"
    AUTO = "auto"

class DetailLevel(str, Enum):
    """Detail level options"""
    BRIEF = "brief"
    STANDARD = "standard"
    DETAILED = "detailed"

def auto_select_method(
    transcription: str,
    custom_prompt: Optional[str] = None,
    chunk_size: int = 4000,
    chunk_overlap: int = 500,
    detail_level: str = DetailLevel.STANDARD,
    temperature: float = 0.2
) -> Tuple[str, Dict[str, Any], List[str]]:
    """
    Automatically select the best summarization method based on transcript characteristics.
    
    Args:
        transcription: Full episode transcription text
        custom_prompt: Optional custom prompt for summarization
        chunk_size: Size of text chunks for processing
        chunk_overlap: Overlap between text chunks
        detail_level: Level of detail in the summary
        temperature: Temperature for the LLM
        
    Returns:
        Tuple containing (summary text, key points dictionary, highlights list)
    """
    import re
    
    logger.info("Auto-selecting summarization method")
    
    # Analyze transcript characteristics
    transcript_length = len(transcription)
    has_speakers = bool(re.search(r'(?:Speaker|Host|Guest)[\s\w]*:', transcription))
    
    # Make a decision based on transcript characteristics
    if SPACY_TRANSFORMERS_AVAILABLE and has_speakers:
        logger.info("Detected speaker annotations, using spaCy method")
        return summarize_with_spacy(
            transcription, 
            custom_prompt, 
            chunk_size, 
            chunk_overlap, 
            detail_level,
            temperature
        )
    elif LLAMAINDEX_AVAILABLE and transcript_length > 50000:
        logger.info("Detected long transcript, using LlamaIndex method")
        return summarize_with_llamaindex(
            transcription, 
            custom_prompt, 
            chunk_size // 4, 
            chunk_overlap // 4, 
            detail_level,
            temperature
        )
    else:
        logger.info("Using LangChain method (default)")
        return summarize_with_langchain(
            transcription, 
            custom_prompt, 
            chunk_size, 
            chunk_overlap, 
            detail_level,
            temperature
        )

def generate_episode_summary(
    transcription: str, 
    custom_prompt: Optional[str] = None, 
    chunk_size: int = 4000, 
    chunk_overlap: int = 500,
    detail_level: str = DetailLevel.STANDARD,
    method: str = SummarizationMethod.AUTO,
    temperature: float = 0.2
) -> Tuple[str, Dict[str, Any], List[str]]:
    """
    Generate a summary from a podcast episode transcription using the specified method.
    
    Args:
        transcription: Full episode transcription text
        custom_prompt: Optional custom prompt for summarization
        chunk_size: Size of text chunks for processing
        chunk_overlap: Overlap between text chunks
        detail_level: Level of detail in the summary (brief, standard, detailed)
        method: Summarization method to use (langchain, llamaindex, spacy, ensemble, auto)
        temperature: Temperature for the LLM
        
    Returns:
        Tuple containing (summary text, key points dictionary, highlights list)
    """
    try:
        logger.info(f"Generating summary with method: {method}, detail level: {detail_level}")
        
        # Validate detail level
        if detail_level not in [d.value for d in DetailLevel]:
            logger.warning(f"Invalid detail level: {detail_level}, defaulting to 'standard'")
            detail_level = DetailLevel.STANDARD
        
        # Call the appropriate method
        if method == SummarizationMethod.LANGCHAIN:
            return summarize_with_langchain(
                transcription, 
                custom_prompt, 
                chunk_size, 
                chunk_overlap, 
                detail_level,
                temperature
            )
        elif method == SummarizationMethod.LLAMAINDEX:
            if not LLAMAINDEX_AVAILABLE:
                logger.warning("LlamaIndex not available, falling back to LangChain")
                return summarize_with_langchain(
                    transcription, 
                    custom_prompt, 
                    chunk_size, 
                    chunk_overlap, 
                    detail_level,
                    temperature
                )
            return summarize_with_llamaindex(
                transcription, 
                custom_prompt, 
                chunk_size // 4,  # Convert to tokens
                chunk_overlap // 4, 
                detail_level,
                temperature
            )
        elif method == SummarizationMethod.SPACY:
            if not SPACY_TRANSFORMERS_AVAILABLE:
                logger.warning("spaCy/Transformers not available, falling back to LangChain")
                return summarize_with_langchain(
                    transcription, 
                    custom_prompt, 
                    chunk_size, 
                    chunk_overlap, 
                    detail_level,
                    temperature
                )
            return summarize_with_spacy(
                transcription, 
                custom_prompt, 
                chunk_size, 
                chunk_overlap, 
                detail_level,
                temperature
            )
        elif method == SummarizationMethod.ENSEMBLE:
            return summarize_with_ensemble(
                transcription, 
                custom_prompt, 
                chunk_size, 
                chunk_overlap, 
                detail_level,
                temperature
            )
        else:  # auto or any other value
            return auto_select_method(
                transcription, 
                custom_prompt, 
                chunk_size, 
                chunk_overlap, 
                detail_level,
                temperature
            )
    
    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}", exc_info=True)
        raise