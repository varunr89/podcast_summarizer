"""
Ensemble-based summarizer that combines multiple methods for podcast transcriptions.
"""
from typing import Tuple, Dict, Any, List, Optional
import re

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from ..processors.langchain_summarizer import summarize_with_langchain, LLAMAINDEX_AVAILABLE
from ..processors.spacy_transformer_summarizer import summarize_with_spacy, SPACY_TRANSFORMERS_AVAILABLE

try:
    from ..processors.llamaindex_summarizer import summarize_with_llamaindex
except ImportError:
    pass

from ..core.logging_config import get_logger
from ..core.llm_provider import get_azure_llm

logger = get_logger(__name__)

def summarize_with_ensemble(
    transcription: str,
    custom_prompt: Optional[str] = None,
    chunk_size: int = 4000,
    chunk_overlap: int = 500,
    detail_level: str = "standard",
    temperature: float = 0.2
) -> Tuple[str, Dict[str, Any], List[str]]:
    """
    Generate a summary using an ensemble of methods for best results.
    
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
    logger.info(f"Using ensemble method with detail level: {detail_level}")
    
    # Get Azure LLM for combining results
    llm = get_azure_llm(temperature=temperature)
    
    # Run multiple summarization methods
    methods = ["langchain"]
    summaries = {}
    key_points_all = {}
    highlights_all = []
    
    # Always run LangChain
    try:
        logger.info("Running LangChain summarization")
        summary, key_points, highlights = summarize_with_langchain(
            transcription, 
            custom_prompt, 
            chunk_size, 
            chunk_overlap, 
            detail_level,
            temperature
        )
        summaries["langchain"] = summary
        key_points_all["langchain"] = key_points["points"]
        highlights_all.extend(highlights)
    except Exception as e:
        logger.error(f"Error running LangChain summarization: {str(e)}")
        summaries["langchain"] = f"Error: {str(e)}"
    
    # Run LlamaIndex if available
    if LLAMAINDEX_AVAILABLE:
        try:
            logger.info("Running LlamaIndex summarization")
            summary, key_points, highlights = summarize_with_llamaindex(
                transcription, 
                custom_prompt, 
                chunk_size // 4,  # Convert to tokens
                chunk_overlap // 4, 
                detail_level,
                temperature
            )
            summaries["llamaindex"] = summary
            key_points_all["llamaindex"] = key_points["points"]
            highlights_all.extend(highlights)
            methods.append("llamaindex")
        except Exception as e:
            logger.error(f"Error running LlamaIndex summarization: {str(e)}")
    
    # Run spaCy if available
    if SPACY_TRANSFORMERS_AVAILABLE:
        try:
            logger.info("Running spaCy summarization")
            summary, key_points, highlights = summarize_with_spacy(
                transcription, 
                custom_prompt, 
                chunk_size, 
                chunk_overlap, 
                detail_level,
                temperature
            )
            summaries["spacy"] = summary
            key_points_all["spacy"] = key_points["points"]
            highlights_all.extend(highlights)
            methods.append("spacy")
        except Exception as e:
            logger.error(f"Error running spaCy summarization: {str(e)}")
    
    # Combine summaries using LLM
    combined_summaries = ""
    for method in methods:
        combined_summaries += f"\n\n{method.upper()} SUMMARY:\n{summaries[method]}"
    
    # Create ensemble prompt based on detail level
    if custom_prompt:
        ensemble_prompt = custom_prompt + "\n\n" + combined_summaries
    else:
        if detail_level == "brief":
            ensemble_prompt = f"""
            Create a concise 3-4 paragraph summary of this podcast by analyzing multiple summarization methods.
            Incorporate the best insights from each approach and resolve any contradictions.
            Focus on the most important points and maintain a cohesive narrative flow.
            
            {combined_summaries}
            
            FINAL CONCISE SUMMARY:
            """
        elif detail_level == "detailed":
            ensemble_prompt = f"""
            Create a detailed 6-8 paragraph summary of this podcast by analyzing multiple summarization methods.
            Incorporate the best insights from each approach and resolve any contradictions.
            Include all significant discussion topics, key insights, and conclusions.
            Ensure a cohesive overall summary with a clear narrative flow.
            
            {combined_summaries}
            
            FINAL DETAILED SUMMARY:
            """
        else:  # standard
            ensemble_prompt = f"""
            Create a comprehensive 4-6 paragraph summary of this podcast by analyzing multiple summarization methods.
            Incorporate the best insights from each approach and resolve any contradictions.
            Capture the main topics discussed, key points, and important conclusions.
            Maintain a cohesive narrative flow.
            
            {combined_summaries}
            
            FINAL COMPREHENSIVE SUMMARY:
            """
    
    # Generate ensemble summary
    ensemble_prompt_template = ChatPromptTemplate.from_template(ensemble_prompt)
    ensemble_chain = ensemble_prompt_template | llm | StrOutputParser()
    ensemble_summary = ensemble_chain.invoke({})
    
    # Combine key points
    all_points = []
    for method, points in key_points_all.items():
        for point_num, point_text in points.items():
            all_points.append(point_text)
    
    # Generate ensemble key points using LLM
    key_points_prompt = f"""
    Create a list of 5-7 key points from this podcast based on the following extracted points.
    Eliminate redundancies and merge similar points.
    Number each point and provide a brief explanation for each.
    
    EXTRACTED POINTS:
    {'. '.join(all_points)}
    
    FINAL KEY POINTS (numbered list):
    """
    
    key_points_prompt_template = ChatPromptTemplate.from_template(key_points_prompt)
    key_points_chain = key_points_prompt_template | llm | StrOutputParser()
    key_points_text = key_points_chain.invoke({})
    
    # Parse key points
    key_points_dict = {}
    for line in key_points_text.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        # Try to extract numbered points
        match = re.match(r'^(\d+)[\.\)]\s+(.+)$', line)
        if match:
            number, point_text = match.groups()
            key_points_dict[number] = point_text
    
    # If no numbered points were found, create simple entries
    if not key_points_dict:
        points_list = [p.strip() for p in key_points_text.split('\n') if p.strip()]
        for i, point in enumerate(points_list, 1):
            key_points_dict[str(i)] = point
    
    ensemble_key_points = {"points": key_points_dict}
    
    # Remove duplicates from highlights
    unique_highlights = []
    for highlight in highlights_all:
        # Check if this highlight is too similar to any existing highlight
        is_unique = True
        for existing in unique_highlights:
            # Simple similarity check
            if len(set(highlight.lower().split()) & set(existing.lower().split())) / len(set(highlight.lower().split() | set(existing.lower().split()))) > 0.6:
                is_unique = False
                break
        if is_unique:
            unique_highlights.append(highlight)
    
    # Generate ensemble highlights using LLM
    highlights_prompt = f"""
    Select the 3-5 most memorable quotes or insights from these extracted quotes.
    Choose quotes that are thought-provoking, insightful, or represent key moments from the podcast.
    
    EXTRACTED QUOTES:
    {'. '.join(unique_highlights)}
    
    FINAL MEMORABLE QUOTES (one per line):
    """
    
    highlights_prompt_template = ChatPromptTemplate.from_template(highlights_prompt)
    highlights_chain = highlights_prompt_template | llm | StrOutputParser()
    highlights_text = highlights_chain.invoke({})
    ensemble_highlights = [h.strip() for h in highlights_text.split('\n') if h.strip()]
    
    return ensemble_summary, ensemble_key_points, ensemble_highlights