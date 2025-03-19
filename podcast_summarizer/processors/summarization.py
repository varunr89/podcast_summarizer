"""
Central hub for podcast summarization functionality.
This module provides a unified interface for accessing different summarization methods.
"""
from typing import Dict, List, Optional, Union, Tuple, Any
import time
import re
import statistics

from ..core.logging_config import get_logger
from .langchain_summarizer import LangChainSummarizer
from .ensemble_summarizer import EnsembleSummarizer

logger = get_logger(__name__)

# Initialize available summarizers
AVAILABLE_METHODS = {
    "langchain": LangChainSummarizer()
    #,"ensemble": EnsembleSummarizer()
}

# # Try to load optional summarizers
# try:
#     from .llamaindex_summarizer import LlamaIndexSummarizer
#     AVAILABLE_METHODS["llamaindex"] = LlamaIndexSummarizer()
# except ImportError:
#     pass

# try:
#     from .spacy_transformer_summarizer import SpacySummarizer
#     AVAILABLE_METHODS["spacy"] = SpacySummarizer()
# except ImportError:
#     pass

class SummaryResult:
    """Container for summarization results."""
    
    def __init__(
        self, 
        summary: str,
        key_points: Dict[str, str], 
        highlights: List[str], 
        method: str,
        execution_time: float
    ):
        self.summary = summary
        self.key_points = key_points
        self.highlights = highlights
        self.method = method
        self.execution_time = execution_time
    
    def to_dict(self) -> Dict:
        """Convert result to dictionary."""
        return {
            "summary": self.summary,
            "key_points": self.key_points,
            "highlights": self.highlights,
            "metadata": {
                "method": self.method,
                "execution_time_seconds": self.execution_time
            }
        }

def get_available_methods() -> List[str]:
    """Get list of available summarization methods."""
    return list(AVAILABLE_METHODS.keys())

def summarize(
    transcription: str,
    method: str = "ensemble",
    custom_prompt: Optional[str] = None,
    chunk_size: int = 4000,
    chunk_overlap: int = 500,
    detail_level: str = "standard",
    temperature: float = 0.2
) -> SummaryResult:
    """
    Generate a summary of the podcast transcription using the specified method.
    
    Args:
        transcription: Full podcast transcription
        method: Summarization method to use ('ensemble', 'langchain', 'llamaindex', 'spacy')
        custom_prompt: Optional custom prompt to use for summarization
        chunk_size: Size of text chunks for processing
        chunk_overlap: Overlap between text chunks
        detail_level: Level of detail in summary ('brief', 'standard', 'detailed')
        temperature: Temperature for LLM generation

    Returns:
        SummaryResult object containing summary, key points, and highlights
    
    Raises:
        ValueError: If the specified method is not available
    """
    if method not in AVAILABLE_METHODS:
        available = ", ".join(get_available_methods())
        raise ValueError(f"Method '{method}' is not available. Choose from: {available}")
    
    # Select the appropriate summarizer
    summarizer = AVAILABLE_METHODS[method]
    
    # Adjust chunk size for LlamaIndex (which uses tokens, not characters)
    current_chunk_size = chunk_size
    current_chunk_overlap = chunk_overlap
    if method == "llamaindex":
        current_chunk_size = chunk_size // 4  # Approximate tokens from characters
        current_chunk_overlap = chunk_overlap // 4
    
    # Track execution time
    start_time = time.time()
    
    # Generate summary
    logger.info(f"Generating summary using {method} method with {detail_level} detail level")
    summary, key_points_dict, highlights = summarizer.summarize_sync(
        transcription=transcription,
        custom_prompt=custom_prompt,
        chunk_size=current_chunk_size,
        chunk_overlap=current_chunk_overlap,
        detail_level=detail_level,
        temperature=temperature
    )
    # For testing: create dummy values instead of calling summarizer
    # summary = "This is a dummy summary of the podcast episode for testing purposes."
    # key_points_dict = {
    #     "points": {
    #         "Key Point 1": "First important point from the discussion.",
    #         "Key Point 2": "Second notable insight from the podcast.",
    #         "Key Point 3": "Third significant concept covered by the speakers."
    #     }
    # }
    # highlights = [
    #     "Highlight quote from the podcast.",
    #     "Another interesting excerpt from the discussion.",
    #     "A third memorable moment from the episode."
    # ]
    # Calculate execution time
    execution_time = time.time() - start_time
    logger.info(f"Summary generation completed in {execution_time:.2f} seconds")
    
    return SummaryResult(
        summary=summary,
        key_points=key_points_dict["points"],
        highlights=highlights,
        method=method,
        execution_time=execution_time
    )

def analyze_transcript_features(transcription: str) -> Dict[str, Any]:
    """
    Analyze a transcript and extract features useful for summarization method selection
    and contextual understanding.
    
    Args:
        transcription: Full episode transcription text
        
    Returns:
        Dictionary containing transcript features
    """
    logger.info("Analyzing transcript features")
    
    features = {}
    
    # Basic metrics
    features["length"] = len(transcription)
    features["word_count"] = len(transcription.split())
    
    # Estimate number of sentences
    sentences = re.split(r'[.!?]+', transcription)
    sentences = [s.strip() for s in sentences if s.strip()]
    features["sentence_count"] = len(sentences)
    
    # Analyze sentence length
    sentence_lengths = [len(s.split()) for s in sentences]
    if sentence_lengths:
        features["avg_sentence_length"] = statistics.mean(sentence_lengths)
        features["max_sentence_length"] = max(sentence_lengths)
        features["min_sentence_length"] = min(sentence_lengths)
    
    # Detect speaker formatting
    speaker_patterns = [
        r'(?:Speaker|Host|Guest)[\s\w]*:',  # Common podcast speaker patterns
        r'[A-Z][a-z]+:',  # Single capitalized word followed by colon (e.g., "John:")
        r'[A-Z][a-z]+ [A-Z][a-z]+:',  # Two capitalized words followed by colon (e.g., "John Smith:")
    ]
    
    features["has_speaker_annotations"] = False
    features["speaker_count"] = 0
    
    for pattern in speaker_patterns:
        speakers = set(re.findall(pattern, transcription))
        if speakers:
            features["has_speaker_annotations"] = True
            features["speaker_count"] = max(features["speaker_count"], len(speakers))
            features["speaker_pattern"] = pattern
            break
    
    # Identify sections or chapters (potential topic transitions)
    section_patterns = [
        r'Chapter \d+',
        r'Section \d+',
        r'Part \d+',
        r'\[\d+:\d+\]',  # Timestamp pattern
        r'\(\d+:\d+\)'   # Another timestamp pattern
    ]
    
    sections = []
    for pattern in section_patterns:
        found_sections = re.findall(pattern, transcription)
        if found_sections:
            sections.extend(found_sections)
    
    features["has_sections"] = len(sections) > 0
    features["section_count"] = len(sections)
    
    # Analyze potential topic complexity
    # This is a simple heuristic based on unique words versus total words
    words = transcription.lower().split()
    unique_words = set(words)
    features["unique_word_count"] = len(unique_words)
    
    if features["word_count"] > 0:
        features["lexical_diversity"] = len(unique_words) / features["word_count"]
    
    # Detect technical content
    technical_terms_patterns = [
        r'\b(?:algorithm|dataset|neural network|machine learning|AI|API|function|code|programming|database|server|client|backend|frontend)\b',
        r'\b(?:statistical|coefficient|correlation|regression|variable|hypothesis|analysis|experiment)\b',
        r'\b(?:genome|protein|molecule|enzyme|biochemical|cellular|neural|clinical|diagnostic)\b'
    ]
    
    technical_term_count = 0
    for pattern in technical_terms_patterns:
        technical_term_count += len(re.findall(pattern, transcription, re.IGNORECASE))
    
    features["technical_term_count"] = technical_term_count
    features["technical_density"] = technical_term_count / features["word_count"] if features["word_count"] > 0 else 0
    features["is_technical"] = features["technical_density"] > 0.01  # Arbitrary threshold
    
    # Detect question-answer format (common in interviews)
    question_patterns = [
        r'\?[\s\n]+[A-Z]',  # Question mark followed by a new sentence
        r'(?:What|How|Why|When|Where|Who|Could you|Can you|Do you).*?\?'
    ]
    
    question_count = 0
    for pattern in question_patterns:
        question_count += len(re.findall(pattern, transcription))
    
    features["question_count"] = question_count
    features["is_interview_style"] = question_count > 5 and question_count / features["sentence_count"] > 0.1 if features["sentence_count"] > 0 else False
    
    # Determine recommended chunk settings based on transcript features
    if features["length"] > 100000:
        # Very long transcript
        features["recommended_chunk_size"] = 6000
        features["recommended_chunk_overlap"] = 800
    elif features["length"] > 50000:
        # Long transcript
        features["recommended_chunk_size"] = 5000
        features["recommended_chunk_overlap"] = 600
    else:
        # Standard transcript
        features["recommended_chunk_size"] = 4000
        features["recommended_chunk_overlap"] = 500
    
    # Recommend best summarization method
    if features["has_speaker_annotations"] and features["speaker_count"] >= 2:
        features["recommended_method"] = "spacy"
        features["method_reason"] = "Speaker annotations detected with multiple speakers"
    elif features["length"] > 50000:
        features["recommended_method"] = "llamaindex"
        features["method_reason"] = "Long transcript detected"
    elif features["is_technical"]:
        features["recommended_method"] = "ensemble"
        features["method_reason"] = "Technical content detected, multiple methods may provide better results"
    else:
        features["recommended_method"] = "langchain"
        features["method_reason"] = "Standard transcript"
    
    logger.info(f"Analysis complete. Recommended method: {features['recommended_method']}")
    return features

def get_recommended_settings(transcription: str) -> Tuple[str, int, int]:
    """
    Get recommended summarization method and chunk settings for a transcript.
    
    Args:
        transcription: Full episode transcription text
        
    Returns:
        Tuple containing (recommended_method, chunk_size, chunk_overlap)
    """
    features = analyze_transcript_features(transcription)
    
    return (
        features["recommended_method"],
        features["recommended_chunk_size"],
        features["recommended_chunk_overlap"]
    )