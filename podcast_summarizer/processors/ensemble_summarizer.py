"""
Ensemble-based summarizer that combines multiple methods for podcast transcriptions.
"""
from typing import Tuple, Dict, Any, List, Optional, Set
import asyncio
from concurrent.futures import ThreadPoolExecutor

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from .langchain_summarizer import LangChainSummarizer
from .base_summarizer import BaseSummarizer
from .prompt_templates import PromptTemplates
from .text_utils import deduplicate_highlights

from ..core.logging_config import get_logger
from ..core.llm_provider import get_azure_llm

logger = get_logger(__name__)

# Lazy imports to avoid dependency issues
_LLAMAINDEX_SUMMARIZER = None
_SPACY_SUMMARIZER = None

class EnsembleSummarizer(BaseSummarizer):
    """Ensemble-based summarizer implementation with parallel processing."""
    
    def __init__(self):
        """Initialize ensemble summarizer with available methods."""
        super().__init__("ensemble")
        self.summarizers = {}
        self.available_methods = set()
        
        # Initialize LangChain summarizer (always available)
        self.summarizers["langchain"] = LangChainSummarizer()
        self.available_methods.add("langchain")
        
        # Try to initialize LlamaIndex summarizer
        try:
            from .llamaindex_summarizer import LlamaIndexSummarizer
            self.summarizers["llamaindex"] = LlamaIndexSummarizer()
            self.available_methods.add("llamaindex")
            logger.info("LlamaIndex summarizer is available")
        except ImportError:
            logger.info("LlamaIndex is not available")
        
        # Try to initialize spaCy summarizer
        try:
            from .spacy_transformer_summarizer import SpacySummarizer
            self.summarizers["spacy"] = SpacySummarizer()
            self.available_methods.add("spacy")
            logger.info("spaCy summarizer is available")
        except ImportError:
            logger.info("spaCy is not available")
            
        logger.info(f"Initialized ensemble summarizer with methods: {', '.join(self.available_methods)}")
    
    def summarize(
        self,
        transcription: str,
        custom_prompt: Optional[str] = None,
        chunk_size: int = 4000,
        chunk_overlap: int = 500,
        detail_level: str = "standard",
        temperature: float = 0.2
    ) -> Tuple[str, Dict[str, Any], List[str]]:
        """
        Generate a summary using an ensemble of methods for best results.
        """
        logger.info(f"Using ensemble method with detail level: {detail_level}")
        
        # Get Azure LLM for combining results
        llm = get_azure_llm(temperature=temperature)
        
        # Run summarization methods in parallel
        results = self._run_summarizers_parallel(
            transcription, 
            custom_prompt,
            chunk_size, 
            chunk_overlap,
            detail_level,
            temperature
        )
        
        # Extract successful results
        summaries = {method: result[0] for method, result in results.items()}
        key_points_all = {method: result[1]["points"] for method, result in results.items()}
        highlights_all = []
        for result in results.values():
            highlights_all.extend(result[2])
        
        # Proceed only if we have at least one successful result
        if not summaries:
            raise RuntimeError("No summarization methods were successful")
        
        # Combine summaries
        combined_summaries = ""
        for method, summary in summaries.items():
            combined_summaries += f"\n\n{method.upper()} SUMMARY:\n{summary}"
        
        # Create ensemble prompt and generate summary
        ensemble_prompt = PromptTemplates.get_ensemble_prompt(
            detail_level, combined_summaries, custom_prompt
        )
        ensemble_summary = (
            ChatPromptTemplate.from_template(ensemble_prompt) 
            | llm 
            | StrOutputParser()
        ).invoke({})
        
        # Combine and process key points
        ensemble_key_points = self._process_key_points(key_points_all, llm)
        
        # Process highlights
        ensemble_highlights = self._process_highlights(highlights_all, llm)
        
        return ensemble_summary, ensemble_key_points, ensemble_highlights
    
    def _run_summarizers_parallel(
        self, 
        transcription: str,
        custom_prompt: Optional[str],
        chunk_size: int,
        chunk_overlap: int,
        detail_level: str,
        temperature: float
    ) -> Dict[str, Tuple[str, Dict[str, Any], List[str]]]:
        """Run available summarizers in parallel and return successful results."""
        results = {}
        
        def run_summarizer(method):
            try:
                logger.info(f"Running {method} summarization")
                
                # Use appropriate chunk size for LlamaIndex (converts to tokens)
                current_chunk_size = chunk_size // 4 if method == "llamaindex" else chunk_size
                current_chunk_overlap = chunk_overlap // 4 if method == "llamaindex" else chunk_overlap
                
                summarizer = self.summarizers[method]
                return method, summarizer.summarize(
                    transcription, 
                    custom_prompt, 
                    current_chunk_size, 
                    current_chunk_overlap, 
                    detail_level,
                    temperature
                )
            except Exception as e:
                logger.error(f"Error running {method} summarization: {str(e)}")
                return None
        
        # Run summarizers in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=len(self.available_methods)) as executor:
            futures = [executor.submit(run_summarizer, method) for method in self.available_methods]
            for future in futures:
                result = future.result()
                if result:
                    method, summary_data = result
                    results[method] = summary_data
        
        return results
    
    def _process_key_points(self, key_points_all: Dict[str, Dict[str, str]], llm) -> Dict[str, Any]:
        """Process and merge key points from all summarizers."""
        # Combine key points
        all_points = []
        for points in key_points_all.values():
            all_points.extend(points.values())
        
        if not all_points:
            return {"points": {}}
        
        # Generate ensemble key points
        key_points_prompt = f"""
        Create a list of 5-7 key points from this podcast based on the following extracted points.
        Eliminate redundancies and merge similar points.
        Number each point and provide a brief explanation for each.
        
        EXTRACTED POINTS:
        {'. '.join(all_points)}
        
        FINAL KEY POINTS (numbered list):
        """
        
        key_points_text = (
            ChatPromptTemplate.from_template(key_points_prompt) 
            | llm 
            | StrOutputParser()
        ).invoke({})
        
        return {"points": self.parse_key_points(key_points_text)}
    
    def _process_highlights(self, highlights_all: List[str], llm) -> List[str]:
        """Process and select the best highlights."""
        if not highlights_all:
            return []
            
        # Remove duplicates
        unique_highlights = deduplicate_highlights(highlights_all)
        
        # If we have few highlights, just return them
        if len(unique_highlights) <= 5:
            return unique_highlights
        
        # Generate ensemble highlights if we have too many
        highlights_prompt = f"""
        Select the 3-5 most memorable quotes or insights from these extracted quotes.
        Choose quotes that are thought-provoking, insightful, or represent key moments from the podcast.
        
        EXTRACTED QUOTES:
        {'. '.join(unique_highlights)}
        
        FINAL MEMORABLE QUOTES (one per line):
        """
        
        highlights_text = (
            ChatPromptTemplate.from_template(highlights_prompt) 
            | llm 
            | StrOutputParser()
        ).invoke({})
        
        return self.parse_highlights(highlights_text)