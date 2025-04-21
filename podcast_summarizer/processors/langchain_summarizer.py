"""
LangGraph-based summarizer for podcast transcriptions with FastAPI compatibility.
"""
from typing import Tuple, Dict, Any, List, Optional, TypedDict, Annotated, Literal
import operator
import functools
import asyncio
import nest_asyncio

from langchain_core.documents import Document
from langchain.prompts import PromptTemplate
from langchain.chains.combine_documents.reduce import split_list_of_docs
from langgraph.graph import StateGraph, START, END
from langgraph.constants import Send

from ..core.logging_config import get_logger
from ..core.llm_provider import get_azure_llm
from .base_summarizer import BaseSummarizer
from .prompt_templates import PromptTemplates
from .text_utils import split_text

logger = get_logger(__name__)

# Apply nest_asyncio to allow nested event loops - needed for FastAPI compatibility
try:
    nest_asyncio.apply()
except Exception as e:
    logger.warning(f"Failed to apply nest_asyncio: {e}")

# Check if LlamaIndex is available (for dependency reporting only)
try:
    import llama_index
    LLAMAINDEX_AVAILABLE = True
except ImportError:
    LLAMAINDEX_AVAILABLE = False

class LangChainSummarizer(BaseSummarizer):
    """LangGraph-based summarizer implementation with FastAPI compatibility."""
    
    def __init__(self):
        super().__init__("langchain")
    
    # This is now our main interface - it's async to work in FastAPI
    async def summarize(
        self,
        transcription: str,
        custom_prompt: Optional[str] = None,
        chunk_size: int = 4000,
        chunk_overlap: int = 500,
        detail_level: str = "standard",
        temperature: float = 0.2
    ) -> Tuple[str, Dict[str, Any], List[str]]:
        """
        Generate a summary using LangGraph's map-reduce approach.
        This is an async method designed to work in FastAPI or other async environments.
        """
        logger.info(f"Using LangGraph method with detail level: {detail_level}")
        
        # Get the LLM
        llm = get_azure_llm(temperature=temperature)
        
        # Split into chunks
        docs = split_text(transcription, chunk_size, chunk_overlap)
        total_chunks = len(docs)
        
        # Add metadata to the documents
        for i, doc in enumerate(docs):
            doc.metadata["chunk_id"] = i + 1
            doc.metadata["total_chunks"] = total_chunks
            doc.metadata["is_first"] = i == 0
            doc.metadata["is_last"] = i == len(docs) - 1

        logger.info(f"Split transcription into {len(docs)} chunks")
        
        # Configure prompts
        map_template = PromptTemplates.get_map_prompt(self.name, detail_level, custom_prompt)
        combine_template = PromptTemplates.get_combine_prompt(self.name, detail_level, custom_prompt)
        
        # Define state types for the graph
        class OverallState(TypedDict):
            documents: List[Document]
            summaries: Annotated[list, operator.add]
            collapsed_summaries: List[Document]
            final_summary: str
            
        class SummaryState(TypedDict):
            document: Document
            
        # Create the summary graph
        token_max = 4000
        
        # Create prompt templates
        map_prompt = PromptTemplate(
            template=map_template,
            input_variables=["text","chunk_id"],
            partial_variables={"total_chunks": str(total_chunks)}
        )
        
        reduce_prompt = PromptTemplate(
            input_variables=["text"],
            template=combine_template
        )
        
        # Generate summary for a single document
        async def generate_summary(state: SummaryState):
            doc = state["document"]
            text = doc.page_content
            chunk_id = doc.metadata["chunk_id"]
            prompt = map_prompt.format(text=text, chunk_id=chunk_id)
            logger.info(f"Generating summary for chunk {chunk_id}/{total_chunks}")
            try:
                response = await llm.ainvoke(prompt)
                return {"summaries": [response.content]}
            except Exception as e:
                logger.error(f"Failed to generate summary for chunk {chunk_id}: {e}")
                return {"summaries": []}
        
        # Map documents to summaries
        def map_summaries(state: OverallState):
            return [
                Send("generate_summary", {"document": doc}) 
                for doc in state["documents"]
            ]
        
        # Collect summaries
        def collect_summaries(state: OverallState):
            return {
                "collapsed_summaries": [Document(page_content=summary) for summary in state["summaries"]]
            }
        
        # Document length function
        def length_function(documents: List[Document]) -> int:
            return sum(llm.get_num_tokens(doc.page_content) for doc in documents)
        
        # Reduce operation
        async def _reduce(input_docs: List[Document]) -> str:
            combined_text = "\n\n".join([doc.page_content for doc in input_docs])
            prompt = reduce_prompt.format(text=combined_text)
            response = await llm.ainvoke(prompt)
            return response.content
        
        # Collapse summaries
        async def collapse_summaries(state: OverallState):
            doc_lists = split_list_of_docs(
                state["collapsed_summaries"], length_function, token_max
            )
            results = []
            for doc_list in doc_lists:
                collapsed_content = await _reduce(doc_list)
                results.append(Document(page_content=collapsed_content))
            
            return {"collapsed_summaries": results}
        
        # Determine if we need to collapse further
        def should_collapse(
            state: OverallState,
        ) -> Literal["collapse_summaries", "generate_final_summary"]:
            num_tokens = length_function(state["collapsed_summaries"])
            if num_tokens > token_max:
                return "collapse_summaries"
            else:
                return "generate_final_summary"
        
        # Generate final summary
        async def generate_final_summary(state: OverallState):
            response = await _reduce(state["collapsed_summaries"])
            return {"final_summary": response}
        
        # Build the summary graph
        summary_graph = StateGraph(OverallState)
        summary_graph.add_node("generate_summary", generate_summary)
        summary_graph.add_node("collect_summaries", collect_summaries)
        summary_graph.add_node("collapse_summaries", collapse_summaries)
        summary_graph.add_node("generate_final_summary", generate_final_summary)
        
        summary_graph.add_conditional_edges(START, map_summaries, ["generate_summary"])
        summary_graph.add_edge("generate_summary", "collect_summaries")
        summary_graph.add_conditional_edges("collect_summaries", should_collapse)
        summary_graph.add_conditional_edges("collapse_summaries", should_collapse)
        summary_graph.add_edge("generate_final_summary", END)
        
        summary_app = summary_graph.compile()
        
        # Run the summary graph
        summary_result = await summary_app.ainvoke({
            "documents": docs,
            "summaries": [],
            "collapsed_summaries": [],
            "final_summary": ""
        })
        summary_output = summary_result["final_summary"]
        
        # Build the key points graph
        key_points_map_prompt = PromptTemplate(
            template=PromptTemplates.get_key_points_map_prompt(self.name),
            input_variables=["text","chunk_id"],
            partial_variables={"total_chunks": str(total_chunks)}
        )
        
        key_points_reduce_prompt = PromptTemplate(
            input_variables=["text","chunk_id"],
            template=PromptTemplates.get_key_points_combine_prompt(self.name)
        )
        
        async def generate_key_points(state: SummaryState):
            doc = state["document"]
            text = doc.page_content
            chunk_id = doc.metadata["chunk_id"]
            prompt = key_points_map_prompt.format(text=text, chunk_id=chunk_id)
            logger.info(f"Generating key points for chunk {chunk_id}/{total_chunks}")
            try:
                response = await llm.ainvoke(prompt)
                return {"summaries": [response.content]}
            except Exception as e:
                logger.error(f"Failed to generate key points for chunk {chunk_id}: {e}")
                return {"summaries": []}
        
        async def _reduce_key_points(input_docs: List[Document]) -> str:
            combined_text = "\n\n".join([doc.page_content for doc in input_docs])
            prompt = key_points_reduce_prompt.format(text=combined_text)
            response = await llm.ainvoke(prompt)
            return response.content
        
        async def collapse_key_points(state: OverallState):
            doc_lists = split_list_of_docs(
                state["collapsed_summaries"], length_function, token_max
            )
            results = []
            for doc_list in doc_lists:
                collapsed_content = await _reduce_key_points(doc_list)
                results.append(Document(page_content=collapsed_content))
            
            return {"collapsed_summaries": results}
        
        async def generate_final_key_points(state: OverallState):
            response = await _reduce_key_points(state["collapsed_summaries"])
            return {"final_summary": response}
        
        key_points_graph = StateGraph(OverallState)
        key_points_graph.add_node("generate_summary", generate_key_points)
        key_points_graph.add_node("collect_summaries", collect_summaries)
        key_points_graph.add_node("collapse_summaries", collapse_key_points)
        key_points_graph.add_node("generate_final_summary", generate_final_key_points)
        
        key_points_graph.add_conditional_edges(START, map_summaries, ["generate_summary"])
        key_points_graph.add_edge("generate_summary", "collect_summaries")
        key_points_graph.add_conditional_edges("collect_summaries", should_collapse)
        key_points_graph.add_conditional_edges("collapse_summaries", should_collapse)
        key_points_graph.add_edge("generate_final_summary", END)
        
        key_points_app = key_points_graph.compile()
        
        # Run the key points graph
        key_points_result = await key_points_app.ainvoke({
            "documents": docs,
            "summaries": [],
            "collapsed_summaries": [],
            "final_summary": ""
        })
        key_points_text = key_points_result["final_summary"]
        key_points = {"points": self.parse_key_points(key_points_text)}
        
        # Build the highlights graph
        highlights_map_prompt = PromptTemplate(
            template=PromptTemplates.get_highlights_map_prompt(self.name),
            input_variables=["text","chunk_id"],
            partial_variables={"total_chunks": str(total_chunks)}
        )
        
        highlights_reduce_prompt = PromptTemplate(
            input_variables=["text"],
            template=PromptTemplates.get_highlights_combine_prompt(self.name)
        )
        
        async def generate_highlights(state: SummaryState):
            doc = state["document"]
            text = doc.page_content
            chunk_id = doc.metadata["chunk_id"]
            prompt = highlights_map_prompt.format(text=text, chunk_id=chunk_id)
            logger.info(f"Generating highlights for chunk {chunk_id}/{total_chunks}")
            try:
                response = await llm.ainvoke(prompt)
                return {"summaries": [response.content]}
            except Exception as e:
                logger.error(f"Failed to generate highlights for chunk {chunk_id}: {e}")
                return {"summaries": []}
        
        async def _reduce_highlights(input_docs: List[Document]) -> str:
            combined_text = "\n\n".join([doc.page_content for doc in input_docs])
            prompt = highlights_reduce_prompt.format(text=combined_text)
            response = await llm.ainvoke(prompt)
            return response.content
        
        async def collapse_highlights(state: OverallState):
            doc_lists = split_list_of_docs(
                state["collapsed_summaries"], length_function, token_max
            )
            results = []
            for doc_list in doc_lists:
                collapsed_content = await _reduce_highlights(doc_list)
                results.append(Document(page_content=collapsed_content))
            
            return {"collapsed_summaries": results}
        
        async def generate_final_highlights(state: OverallState):
            response = await _reduce_highlights(state["collapsed_summaries"])
            return {"final_summary": response}
        
        highlights_graph = StateGraph(OverallState)
        highlights_graph.add_node("generate_summary", generate_highlights)
        highlights_graph.add_node("collect_summaries", collect_summaries)
        highlights_graph.add_node("collapse_summaries", collapse_highlights)
        highlights_graph.add_node("generate_final_summary", generate_final_highlights)
        
        highlights_graph.add_conditional_edges(START, map_summaries, ["generate_summary"])
        highlights_graph.add_edge("generate_summary", "collect_summaries")
        highlights_graph.add_conditional_edges("collect_summaries", should_collapse)
        highlights_graph.add_conditional_edges("collapse_summaries", should_collapse)
        highlights_graph.add_edge("generate_final_summary", END)
        
        highlights_app = highlights_graph.compile()
        
        # Run the highlights graph
        highlights_result = await highlights_app.ainvoke({
            "documents": docs,
            "summaries": [],
            "collapsed_summaries": [],
            "final_summary": ""
        })
        highlights_text = highlights_result["final_summary"]
        highlights = self.parse_highlights(highlights_text)
        
        return summary_output, key_points, highlights
    
    # Synchronous interface for backward compatibility
    # This is now just a wrapper around the async method
    def summarize_sync(
        self,
        transcription: str,
        custom_prompt: Optional[str] = None,
        chunk_size: int = 4000,
        chunk_overlap: int = 500,
        detail_level: str = "standard",
        temperature: float = 0.2
    ) -> Tuple[str, Dict[str, Any], List[str]]:
        """
        Synchronous version of summarize for backward compatibility.
        Uses nest_asyncio to handle execution within an event loop.
        """
        try:
            # Try to get the event loop
            loop = asyncio.get_event_loop()
            # Use nest_asyncio to run the async method
            return loop.run_until_complete(
                self.summarize(
                    transcription, 
                    custom_prompt, 
                    chunk_size, 
                    chunk_overlap, 
                    detail_level, 
                    temperature
                )
            )
        except RuntimeError as e:
            logger.warning(f"Event loop error: {e}. Creating new event loop.")
            # If no event loop exists, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                self.summarize(
                    transcription, 
                    custom_prompt, 
                    chunk_size, 
                    chunk_overlap, 
                    detail_level, 
                    temperature
                )
            )
            loop.close()
            return result