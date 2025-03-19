"""
LlamaIndex-based summarizer for podcast transcriptions.
"""
from typing import Tuple, Dict, Any, List, Optional

from ..core.logging_config import get_logger
from ..core.llm_provider import get_azure_llm
from .base_summarizer import BaseSummarizer

logger = get_logger(__name__)

# Check if LlamaIndex is available

from llama_index.core import Document as LIDocument, ServiceContext
from llama_index.core.node_parser import SimpleNodeParser
from llama_index.core.indices.document_summary import DocumentSummaryIndex
from llama_index.core.response_synthesizers import TreeSummarize
from llama_index.core.llms import LangChainLLM
LLAMAINDEX_AVAILABLE = True

class LlamaIndexSummarizer(BaseSummarizer):
    """LlamaIndex-based summarizer implementation."""
    
    def __init__(self):
        super().__init__("llamaindex")
        if not LLAMAINDEX_AVAILABLE:
            raise ImportError("LlamaIndex is not installed. Please install it with: pip install llama-index")
    
    def summarize(
        self,
        transcription: str,
        custom_prompt: Optional[str] = None,
        chunk_size: int = 1024,  # LlamaIndex uses tokens not characters
        chunk_overlap: int = 100,
        detail_level: str = "standard",
        temperature: float = 0.2
    ) -> Tuple[str, Dict[str, Any], List[str]]:
        """
        Generate a summary using LlamaIndex's hierarchical summarization.
        """
        logger.info(f"Using LlamaIndex method with detail level: {detail_level}")
        
        # Get service context with LLM
        service_context = self._create_service_context(temperature, chunk_size, chunk_overlap)
        
        # Create document and parse into nodes
        document = LIDocument(text=transcription)
        parser = SimpleNodeParser.from_defaults(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        nodes = parser.get_nodes_from_documents([document])
        logger.info(f"Split transcription into {len(nodes)} nodes")
        
        # Create summary prompt based on detail level
        summary_prompt = self._get_summary_prompt(detail_level, custom_prompt)
        
        # Create the summary index
        summary_index = DocumentSummaryIndex.from_documents(
            [document],
            service_context=service_context,
            summary_query=summary_prompt,
            show_progress=True
        )
        
        # Generate the summary using query
        query = self._get_query(detail_level, custom_prompt)
        detailed_response = summary_index.query(query)
        detailed_summary = str(detailed_response)
        
        # Generate key points
        key_points_text = self._generate_tree_summary(
            service_context,
            detailed_summary,
            """
            Create a structured list of 5-7 key points from the following podcast transcript summary:
            
            {context}
            
            KEY POINTS:
            """
        )
        key_points_dict = self.parse_key_points(str(key_points_text))
        key_points = {"points": key_points_dict}
        
        # Generate highlights
        highlights_text = self._generate_tree_summary(
            service_context,
            detailed_summary,
            """
            Extract 3-5 memorable quotes or insights from the following podcast transcript summary.
            Select quotes that are thought-provoking, insightful, or represent key moments.
            
            {context}
            
            MEMORABLE QUOTES:
            """
        )
        highlights = self.parse_highlights(str(highlights_text))
        
        return detailed_summary, key_points, highlights
    
    def _create_service_context(self, temperature, chunk_size, chunk_overlap):
        """Create LlamaIndex service context with LLM."""
        azure_llm = get_azure_llm(temperature=temperature)
        llm = LangChainLLM(llm=azure_llm)
        
        return ServiceContext.from_defaults(
            llm=llm,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
    
    def _get_summary_prompt(self, detail_level, custom_prompt):
        """Get appropriate summary prompt based on detail level."""
        if custom_prompt:
            return custom_prompt
        
        base_prompt = {
            "brief": "Please provide a concise summary of the following podcast transcript section. Focus only on the most important points.",
            "standard": "Please provide a comprehensive summary of the following podcast transcript section. Capture the main topics discussed, key points, and important conclusions.",
            "detailed": "Please provide a detailed summary of the following podcast transcript section. Include all significant discussion topics, key insights, and conclusions."
        }.get(detail_level, "Please provide a comprehensive summary of the following podcast transcript section.")
        
        return base_prompt + "\n\nText to summarize:\n{text}\n\nSummary:"
    
    def _get_query(self, detail_level, custom_prompt):
        """Get appropriate query for summary generation."""
        if custom_prompt:
            return custom_prompt
        
        return {
            "brief": "Provide a concise 3-4 paragraph summary of the podcast.",
            "standard": "Provide a comprehensive 4-6 paragraph summary of the podcast, capturing the main topics, key points, and important conclusions.",
            "detailed": "Provide a detailed 6-8 paragraph summary of the podcast, including all significant discussion topics, key insights, and conclusions."
        }.get(detail_level, "Provide a comprehensive summary of the podcast.")
    
    def _generate_tree_summary(self, service_context, text, template):
        """Generate summary using TreeSummarize."""
        tree_summarize = TreeSummarize(
            service_context=service_context,
            verbose=True,
            summary_template=template
        )
        return tree_summarize.get_response(text)

# Simplified function that uses the class
def summarize_with_llamaindex(
    transcription: str,
    custom_prompt: Optional[str] = None,
    chunk_size: int = 1024,
    chunk_overlap: int = 100,
    detail_level: str = "standard",
    temperature: float = 0.2
) -> Tuple[str, Dict[str, Any], List[str]]:
    """Function wrapper for backward compatibility."""
    summarizer = LlamaIndexSummarizer()
    return summarizer.summarize(
        transcription, 
        custom_prompt, 
        chunk_size, 
        chunk_overlap, 
        detail_level,
        temperature
    )