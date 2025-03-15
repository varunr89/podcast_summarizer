"""
LangChain-based summarizer for podcast transcriptions.
"""
from typing import Tuple, Dict, Any, List, Optional
import re

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.summarize import load_summarize_chain
from langchain.prompts import PromptTemplate
from langchain.schema import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from ..core.logging_config import get_logger
from ..core.llm_provider import get_azure_llm

logger = get_logger(__name__)

def summarize_with_langchain(
    transcription: str,
    custom_prompt: Optional[str] = None,
    chunk_size: int = 4000,
    chunk_overlap: int = 500,
    detail_level: str = "standard",
    temperature: float = 0.2
) -> Tuple[str, Dict[str, Any], List[str]]:
    """
    Generate a summary using LangChain's map-reduce approach.
    
    Args:
        transcription: Full episode transcription text
        custom_prompt: Optional custom prompt for summarization
        chunk_size: Size of text chunks for processing
        chunk_overlap: Overlap between text chunks
        detail_level: Level of detail in the summary (brief, standard, detailed)
        temperature: Temperature for the LLM
        
    Returns:
        Tuple containing (summary text, key points dictionary, highlights list)
    """
    logger.info(f"Using LangChain method with detail level: {detail_level}")
    
    # Get the LLM
    llm = get_azure_llm(temperature=temperature)
    
    # Create text splitter with improved semantic boundary awareness
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", "! ", "? ", ";", ":", " ", ""]
    )
    
    # Split into chunks
    docs = text_splitter.create_documents([transcription])
    logger.info(f"Split transcription into {len(docs)} chunks")
    
    # Add metadata to the documents
    for i, doc in enumerate(docs):
        doc.metadata["chunk_id"] = i + 1
        doc.metadata["total_chunks"] = len(docs)
        doc.metadata["is_first"] = i == 0
        doc.metadata["is_last"] = i == len(docs) - 1
    
    # Define prompt templates based on detail level
    if custom_prompt:
        map_template = custom_prompt
        combine_template = custom_prompt
    else:
        # Map prompt (for individual chunks)
        if detail_level == "brief":
            map_template = """
            You're summarizing part {chunk_id} of {total_chunks} of a podcast transcript.
            
            Write a concise summary of this section, capturing only the essential points.
            
            TRANSCRIPT SECTION:
            {text}
            
            CONCISE SECTION SUMMARY:
            """
        elif detail_level == "detailed":
            map_template = """
            You're summarizing part {chunk_id} of {total_chunks} of a podcast transcript.
            
            Write a detailed summary of this section, capturing all significant topics,
            key points, quotes, insights, and maintaining the conversational flow.
            
            TRANSCRIPT SECTION:
            {text}
            
            DETAILED SECTION SUMMARY:
            """
        else:  # standard
            map_template = """
            You're summarizing part {chunk_id} of {total_chunks} of a podcast transcript.
            
            Write a comprehensive summary of this section, capturing the main topics discussed,
            key points, and maintaining the context of the conversation.
            
            TRANSCRIPT SECTION:
            {text}
            
            COMPREHENSIVE SECTION SUMMARY:
            """
        
        # Combine prompt for merging chunk summaries
        if detail_level == "brief":
            combine_template = """
            Create a concise 3-4 paragraph summary of this podcast by combining these section summaries.
            Focus on the most important points and maintain a cohesive narrative flow.
            Eliminate redundancies between sections.
            
            SECTION SUMMARIES:
            {text}
            
            FINAL CONCISE SUMMARY:
            """
        elif detail_level == "detailed":
            combine_template = """
            Create a detailed 6-8 paragraph summary of this podcast by combining these section summaries.
            Include all significant discussion topics, key insights, and conclusions.
            Eliminate redundancies and ensure a cohesive overall summary with a clear narrative flow.
            
            SECTION SUMMARIES:
            {text}
            
            FINAL DETAILED SUMMARY:
            """
        else:  # standard
            combine_template = """
            Create a comprehensive 4-6 paragraph summary of this podcast by combining these section summaries.
            Capture the main topics discussed, key points, and important conclusions.
            Maintain a cohesive narrative flow and eliminate redundancies.
            
            SECTION SUMMARIES:
            {text}
            
            FINAL COMPREHENSIVE SUMMARY:
            """
    
    # Create map prompt with metadata variables
    map_prompt = PromptTemplate(
        input_variables=["text"],
        partial_variables={
            "chunk_id": lambda x: x.metadata["chunk_id"], 
            "total_chunks": lambda x: x.metadata["total_chunks"]
        },
        template=map_template
    )
    
    # Create combine prompt
    combine_prompt = PromptTemplate(
        input_variables=["text"],
        template=combine_template
    )
    
    # Create the chain
    map_reduce_chain = load_summarize_chain(
        llm,
        chain_type="map_reduce",
        map_prompt=map_prompt,
        combine_prompt=combine_prompt,
        verbose=True
    )
    
    # Generate summary
    summary_output = map_reduce_chain.run(docs)
    
    # Generate key points
    key_points_map_template = """
    You're analyzing part {chunk_id} of {total_chunks} of a podcast transcript.
    
    Extract 2-3 key points from this section of the transcript.
    Focus on important insights, arguments, or conclusions.
    
    TRANSCRIPT SECTION:
    {text}
    
    KEY POINTS:
    """
    
    key_points_combine_template = """
    From these extracted key points, create a consolidated list of 5-7 most important key points from the podcast.
    Eliminate redundancies and merge similar points.
    Number each point and provide a brief explanation for each.
    
    EXTRACTED POINTS:
    {text}
    
    FINAL KEY POINTS (numbered list):
    """
    
    key_points_map_prompt = PromptTemplate(
        input_variables=["text"],
        partial_variables={
            "chunk_id": lambda x: x.metadata["chunk_id"], 
            "total_chunks": lambda x: x.metadata["total_chunks"]
        },
        template=key_points_map_template
    )
    
    key_points_combine_prompt = PromptTemplate(
        input_variables=["text"],
        template=key_points_combine_template
    )
    
    key_points_chain = load_summarize_chain(
        llm,
        chain_type="map_reduce",
        map_prompt=key_points_map_prompt,
        combine_prompt=key_points_combine_prompt,
        verbose=True
    )
    
    key_points_text = key_points_chain.run(docs)
    
    # Parse key points into a dictionary
    key_points_dict = {}
    for line in key_points_text.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        # Try to extract numbered points (1. Point text or 1) Point text)
        match = re.match(r'^(\d+)[\.\)]?\s+(.+)$', line)
        if match:
            number, point_text = match.groups()
            key_points_dict[number] = point_text
    
    # If no numbered points were found, create simple entries
    if not key_points_dict:
        points_list = [p.strip() for p in key_points_text.split('\n') if p.strip()]
        for i, point in enumerate(points_list, 1):
            key_points_dict[str(i)] = point
    
    key_points = {"points": key_points_dict}
    
    # Generate highlights/memorable quotes
    highlights_map_template = """
    You're analyzing part {chunk_id} of {total_chunks} of a podcast transcript.
    
    Extract 1-2 memorable quotes or insights from this section that are particularly
    insightful, thought-provoking, or representative of key moments.
    
    TRANSCRIPT SECTION:
    {text}
    
    MEMORABLE QUOTES:
    """
    
    highlights_combine_template = """
    From these extracted quotes and insights, select the 3-5 most memorable ones
    that best represent the key insights or moments from the podcast.
    Prioritize direct quotations when possible.
    List each quote on a separate line.
    
    EXTRACTED QUOTES:
    {text}
    
    FINAL MEMORABLE QUOTES (one per line):
    """
    
    highlights_map_prompt = PromptTemplate(
        input_variables=["text"],
        partial_variables={
            "chunk_id": lambda x: x.metadata["chunk_id"], 
            "total_chunks": lambda x: x.metadata["total_chunks"]
        },
        template=highlights_map_template
    )
    
    highlights_combine_prompt = PromptTemplate(
        input_variables=["text"],
        template=highlights_combine_template
    )
    
    highlights_chain = load_summarize_chain(
        llm,
        chain_type="map_reduce",
        map_prompt=highlights_map_prompt,
        combine_prompt=highlights_combine_prompt,
        verbose=True
    )
    
    highlights_text = highlights_chain.run(docs)
    highlights = [h.strip() for h in highlights_text.split('\n') if h.strip()]
    
    return summary_output, key_points, highlights