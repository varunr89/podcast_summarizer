"""
LlamaIndex-based summarizer for podcast transcriptions.
"""
from typing import Tuple, Dict, Any, List, Optional
import re

# Check if LlamaIndex is available
try:
    from llama_index.core import Document as LIDocument, ServiceContext
    from llama_index.core.node_parser import SimpleNodeParser
    from llama_index.core.indices.document_summary import DocumentSummaryIndex
    from llama_index.core.response_synthesizers import TreeSummarize
    from llama_index.core.llms import LangChainLLM
    from llama_index.llms.azure_openai import AzureOpenAI
    LLAMAINDEX_AVAILABLE = True
except ImportError:
    LLAMAINDEX_AVAILABLE = False

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from ..core.logging_config import get_logger
from ..core.llm_provider import get_azure_llm

logger = get_logger(__name__)

def summarize_with_llamaindex(
    transcription: str,
    custom_prompt: Optional[str] = None,
    chunk_size: int = 1024,  # LlamaIndex uses tokens not characters
    chunk_overlap: int = 100,
    detail_level: str = "standard",
    temperature: float = 0.2
) -> Tuple[str, Dict[str, Any], List[str]]:
    """
    Generate a summary using LlamaIndex's hierarchical summarization.
    
    Args:
        transcription: Full episode transcription text
        custom_prompt: Optional custom prompt for summarization
        chunk_size: Size of text chunks in tokens
        chunk_overlap: Overlap between chunks in tokens
        detail_level: Level of detail in the summary (brief, standard, detailed)
        temperature: Temperature for the LLM
        
    Returns:
        Tuple containing (summary text, key points dictionary, highlights list)
    """
    if not LLAMAINDEX_AVAILABLE:
        raise ImportError("LlamaIndex is not installed. Please install it with: pip install llama-index")
    
    logger.info(f"Using LlamaIndex method with detail level: {detail_level}")
    
    # Get Azure LLM
    azure_llm = get_azure_llm(temperature=temperature)
    
    # Wrap LangChain LLM for LlamaIndex
    llm = LangChainLLM(llm=azure_llm)
    
    # Create service context
    service_context = ServiceContext.from_defaults(
        llm=llm,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    
    # Create document
    document = LIDocument(text=transcription)
    
    # Create a node parser
    parser = SimpleNodeParser.from_defaults(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    
    # Parse the document into nodes
    nodes = parser.get_nodes_from_documents([document])
    logger.info(f"Split transcription into {len(nodes)} nodes")
    
    # Create a summary prompt based on detail level
    if custom_prompt:
        summary_prompt = custom_prompt
    else:
        if detail_level == "brief":
            summary_prompt = "Please provide a concise summary of the following podcast transcript section. Focus only on the most important points."
        elif detail_level == "detailed":
            summary_prompt = "Please provide a detailed summary of the following podcast transcript section. Include all significant discussion topics, key insights, and conclusions."
        else:  # standard
            summary_prompt = "Please provide a comprehensive summary of the following podcast transcript section. Capture the main topics discussed, key points, and important conclusions."
    
    # Add general instructions
    summary_prompt += """
    
    Text to summarize:
    {text}
    
    Summary:
    """
    
    # Create the summary index
    summary_index = DocumentSummaryIndex.from_documents(
        [document],
        service_context=service_context,
        summary_query=summary_prompt,
        show_progress=True
    )
    
    # Generate the summary
    if custom_prompt:
        query = custom_prompt
    else:
        if detail_level == "brief":
            query = "Provide a concise 3-4 paragraph summary of the podcast."
        elif detail_level == "detailed":
            query = "Provide a detailed 6-8 paragraph summary of the podcast, including all significant discussion topics, key insights, and conclusions."
        else:  # standard
            query = "Provide a comprehensive 4-6 paragraph summary of the podcast, capturing the main topics, key points, and important conclusions."
    
    detailed_response = summary_index.query(query)
    detailed_summary = str(detailed_response)
    
    # Create hierarchical summarization for key points
    tree_summarize = TreeSummarize(
        service_context=service_context,
        verbose=True,
        summary_template="""
        Create a structured list of 5-7 key points from the following podcast transcript summary:
        
        {context}
        
        KEY POINTS:
        """
    )
    
    # Generate key points from detailed summary
    key_points_text = tree_summarize.get_response(detailed_summary)
    key_points_text = str(key_points_text)
    
    # Parse key points
    key_points_dict = {}
    for i, point in enumerate(key_points_text.split('\n'), 1):
        point = point.strip()
        if point:
            # Remove leading numbers if present
            if re.match(r'^\d+[\.\)]', point):
                point = re.sub(r'^\d+[\.\)]\s*', '', point)
            key_points_dict[str(i)] = point
    
    key_points = {"points": key_points_dict}
    
    # Generate highlights using a similar approach
    highlights_template = """
    Extract 3-5 memorable quotes or insights from the following podcast transcript summary.
    Select quotes that are thought-provoking, insightful, or represent key moments.
    
    {context}
    
    MEMORABLE QUOTES:
    """
    
    highlights_summarize = TreeSummarize(
        service_context=service_context,
        verbose=True,
        summary_template=highlights_template
    )
    
    highlights_text = highlights_summarize.get_response(detailed_summary)
    highlights = [h.strip() for h in str(highlights_text).split('\n') if h.strip()]
    
    return detailed_summary, key_points, highlights