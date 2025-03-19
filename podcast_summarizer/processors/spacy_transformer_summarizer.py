"""
spaCy and Transformers-based summarizer for podcast transcriptions.
"""
from typing import Tuple, Dict, Any, List, Optional
import re

from ..core.logging_config import get_logger
from ..core.llm_provider import get_azure_llm
from .base_summarizer import BaseSummarizer

logger = get_logger(__name__)

# Check if spaCy and transformers are available
import spacy
import torch
from transformers import AutoTokenizer, AutoModel
import numpy as np
from langchain.chains.summarize import load_summarize_chain
from langchain.prompts import PromptTemplate
from langchain.schema import Document
SPACY_TRANSFORMERS_AVAILABLE = True


class SpacySummarizer(BaseSummarizer):
    """spaCy and Transformers-based summarizer implementation."""
    
    def __init__(self):
        super().__init__("spacy")
        if not SPACY_TRANSFORMERS_AVAILABLE:
            raise ImportError("spaCy and transformers are not installed. Please install them with: pip install spacy transformers torch numpy")
        
        # Load spaCy model during initialization to avoid repeated loading
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except:
            logger.info("Downloading spaCy model en_core_web_sm")
            spacy.cli.download("en_core_web_sm")
            self.nlp = spacy.load("en_core_web_sm")
            
        # Initialize tokenizer and model for embeddings
        self.tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
        self.model = AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
    
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
        Generate a summary using spaCy and transformers for advanced NLP processing.
        """
        logger.info(f"Using spaCy method with detail level: {detail_level}")
        
        # Get Azure LLM
        llm = get_azure_llm(temperature=temperature)
        
        # Process transcript with spaCy
        logger.info("Processing transcript with spaCy")
        doc = self.nlp(transcription)
        
        # Extract sentences and create semantic chunks
        sentences = [sent.text for sent in doc.sents]
        logger.info(f"Extracted {len(sentences)} sentences")
        
        # Generate sentence embeddings and find topic shifts
        embeddings = self._get_embeddings(sentences)
        topic_shifts = self._find_topic_shifts(embeddings)
        logger.info(f"Detected {len(topic_shifts)} potential topic shifts")
        
        # Create context-aware chunks
        chunks = self._create_semantic_chunks(
            sentences, topic_shifts, chunk_size, chunk_overlap
        )
        logger.info(f"Created {len(chunks)} context-aware chunks")
        
        # Extract entities
        entities = self._extract_entities(doc)
        
        # Create LangChain documents with metadata
        docs = self._create_documents_with_metadata(chunks)
        
        # Get additional context functions
        topic_shift_note_func = self._get_topic_shift_note
        entities_text_func = self._get_entities_text
        global_entities_func = lambda: self._get_global_entities(docs)
        
        # Create map prompts for summary
        map_template = self._get_map_template(detail_level, custom_prompt)
        map_prompt = PromptTemplate(
            input_variables=["text"],
            partial_variables={
                "chunk_id": lambda x: x.metadata["chunk_id"],
                "total_chunks": lambda x: x.metadata["total_chunks"],
                "topic_shift_note": topic_shift_note_func,
                "entities": entities_text_func
            },
            template=map_template
        )
        
        # Create combine prompt for summary
        combine_template = self._get_combine_template(detail_level, custom_prompt)
        combine_prompt = PromptTemplate(
            input_variables=["text"],
            partial_variables={
                "global_entities": global_entities_func
            },
            template=combine_template
        )
        
        # Create summary chain
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
        key_points_text = self._generate_key_points(
            llm, docs, 
            topic_shift_note_func, 
            entities_text_func, 
            global_entities_func
        )
        key_points = {"points": self.parse_key_points(key_points_text)}
        
        # Generate highlights
        highlights_text = self._generate_highlights(
            llm, docs,
            topic_shift_note_func,
            entities_text_func,
            global_entities_func
        )
        highlights = self.parse_highlights(highlights_text)
        
        return summary_output, key_points, highlights
    
    def _get_embeddings(self, sentences: List[str]) -> np.ndarray:
        """Get embeddings for a list of sentences."""
        embeddings = []
        for sentence in sentences:
            inputs = self.tokenizer(sentence, padding=True, truncation=True, return_tensors="pt")
            with torch.no_grad():
                outputs = self.model(**inputs)
            # Use mean pooling to get sentence embedding
            embeddings.append(outputs.last_hidden_state.mean(dim=1).squeeze().numpy())
        
        return np.array(embeddings)
    
    def _find_topic_shifts(self, embeddings: np.ndarray) -> List[int]:
        """Find points of topic shift based on embedding similarity."""
        # Calculate similarity between adjacent sentences
        similarities = []
        for i in range(len(embeddings) - 1):
            sim = np.dot(embeddings[i], embeddings[i+1]) / (
                np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[i+1])
            )
            similarities.append(sim)
        
        # Find potential topic shifts (points of low similarity)
        topic_shifts = []
        mean_sim = np.mean(similarities)
        std_sim = np.std(similarities)
        threshold = max(0.5, mean_sim - std_sim)  # Set reasonable threshold
        
        for i, sim in enumerate(similarities):
            if sim < threshold:
                topic_shifts.append(i + 1)  # Index of sentence after the shift
        
        return topic_shifts
    
    def _create_semantic_chunks(
        self, 
        sentences: List[str], 
        topic_shifts: List[int],
        chunk_size: int,
        chunk_overlap: int
    ) -> List[Dict]:
        """Create context-aware chunks with topic shift information."""
        chunks = []
        current_chunk = []
        current_size = 0
        is_topic_shift = False
        
        for i, sentence in enumerate(sentences):
            # Check if this is where a topic shift occurs
            if i in topic_shifts:
                is_topic_shift = True
            
            sent_size = len(sentence)
            
            # If adding this sentence would exceed chunk size and we have content
            if current_size + sent_size > chunk_size and current_chunk:
                # Create a chunk
                chunk_text = " ".join(current_chunk)
                chunks.append({
                    "text": chunk_text,
                    "is_topic_shift": is_topic_shift,
                    "index": len(chunks)
                })
                
                # Reset for next chunk with overlap
                overlap_sentences = min(int(chunk_overlap / sent_size) + 1, len(current_chunk))
                current_chunk = current_chunk[-overlap_sentences:]
                current_size = sum(len(s) for s in current_chunk)
                is_topic_shift = False
            
            # Add current sentence
            current_chunk.append(sentence)
            current_size += sent_size
        
        # Add the last chunk if not empty
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append({
                "text": chunk_text,
                "is_topic_shift": is_topic_shift,
                "index": len(chunks)
            })
        
        return chunks
    
    def _extract_entities(self, doc) -> Dict[str, List[str]]:
        """Extract named entities from document."""
        entities = {}
        for ent in doc.ents:
            if ent.label_ not in entities:
                entities[ent.label_] = []
            if ent.text not in entities[ent.label_]:
                entities[ent.label_].append(ent.text)
        return entities
    
    def _create_documents_with_metadata(self, chunks: List[Dict]) -> List[Document]:
        """Create LangChain documents with enhanced metadata."""
        docs = []
        for i, chunk in enumerate(chunks):
            # Extract entities in this chunk
            chunk_doc = self.nlp(chunk["text"])
            chunk_entities = []
            for ent in chunk_doc.ents:
                chunk_entities.append(ent.text)
            
            # Create document with metadata
            doc = Document(
                page_content=chunk["text"],
                metadata={
                    "chunk_id": i + 1,
                    "total_chunks": len(chunks),
                    "is_topic_shift": chunk["is_topic_shift"],
                    "entities": chunk_entities
                }
            )
            docs.append(doc)
        return docs
    
    def _get_topic_shift_note(self, doc):
        """Get note about topic shift."""
        if doc.metadata.get("is_topic_shift", False):
            return "NOTE: This section contains a significant topic transition."
        return "This section continues the previous topic."
    
    def _get_entities_text(self, doc):
        """Get formatted entity text."""
        entities = doc.metadata.get("entities", [])
        if entities:
            return ", ".join(entities[:5])  # Limit to 5 entities
        return "No significant entities detected"
    
    def _get_global_entities(self, docs):
        """Get important global entities."""
        all_entities = []
        for doc in docs:
            all_entities.extend(doc.metadata.get("entities", []))
        
        # Count entities
        entity_counts = {}
        for entity in all_entities:
            entity_counts[entity] = entity_counts.get(entity, 0) + 1
        
        # Sort by frequency
        sorted_entities = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)
        top_entities = [e for e, c in sorted_entities[:10]]  # Top 10 entities
        
        return ", ".join(top_entities) if top_entities else "No significant entities detected"
    
    def _get_map_template(self, detail_level: str, custom_prompt: Optional[str]) -> str:
        """Get map template based on detail level."""
        if custom_prompt:
            return custom_prompt
            
        templates = {
            "brief": """
            You're summarizing part {chunk_id} of {total_chunks} of a podcast transcript.
            
            {topic_shift_note}
            
            Key entities in this section: {entities}
            
            Write a concise summary of this section, capturing only the essential points.
            
            TRANSCRIPT SECTION:
            {text}
            
            CONCISE SECTION SUMMARY:
            """,
            
            "detailed": """
            You're summarizing part {chunk_id} of {total_chunks} of a podcast transcript.
            
            {topic_shift_note}
            
            Key entities in this section: {entities}
            
            Write a detailed summary of this section, capturing all significant topics,
            key points, quotes, insights, and maintaining the conversational flow.
            
            TRANSCRIPT SECTION:
            {text}
            
            DETAILED SECTION SUMMARY:
            """,
            
            "standard": """
            You're summarizing part {chunk_id} of {total_chunks} of a podcast transcript.
            
            {topic_shift_note}
            
            Key entities in this section: {entities}
            
            Write a comprehensive summary of this section, capturing the main topics discussed,
            key points, and maintaining the context of the conversation.
            
            TRANSCRIPT SECTION:
            {text}
            
            COMPREHENSIVE SECTION SUMMARY:
            """
        }
        
        return templates.get(detail_level, templates["standard"])
    
    def _get_combine_template(self, detail_level: str, custom_prompt: Optional[str]) -> str:
        """Get combine template based on detail level."""
        if custom_prompt:
            return custom_prompt
            
        templates = {
            "brief": """
            Create a concise 3-4 paragraph summary of this podcast by combining these section summaries.
            Focus on the most important points and maintain a cohesive narrative flow.
            
            Important entities mentioned: {global_entities}
            
            SECTION SUMMARIES:
            {text}
            
            FINAL CONCISE SUMMARY:
            """,
            
            "detailed": """
            Create a detailed 6-8 paragraph summary of this podcast by combining these section summaries.
            Include all significant discussion topics, key insights, and conclusions.
            Eliminate redundancies and ensure a cohesive overall summary with a clear narrative flow.
            
            Important entities mentioned: {global_entities}
            
            SECTION SUMMARIES:
            {text}
            
            FINAL DETAILED SUMMARY:
            """,
            
            "standard": """
            Create a comprehensive 4-6 paragraph summary of this podcast by combining these section summaries.
            Capture the main topics discussed, key points, and important conclusions.
            Maintain a cohesive narrative flow and eliminate redundancies.
            
            Important entities mentioned: {global_entities}
            
            SECTION SUMMARIES:
            {text}
            
            FINAL COMPREHENSIVE SUMMARY:
            """
        }
        
        return templates.get(detail_level, templates["standard"])
    
    def _generate_key_points(self, llm, docs, topic_shift_func, entities_func, global_entities_func):
        """Generate key points using map-reduce approach."""
        key_points_map_template = """
        You're analyzing part {chunk_id} of {total_chunks} of a podcast transcript.
        
        {topic_shift_note}
        
        Key entities in this section: {entities}
        
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
        
        Important entities mentioned: {global_entities}
        
        EXTRACTED POINTS:
        {text}
        
        FINAL KEY POINTS (numbered list):
        """
        
        key_points_map_prompt = PromptTemplate(
            input_variables=["text"],
            partial_variables={
                "chunk_id": lambda x: x.metadata["chunk_id"],
                "total_chunks": lambda x: x.metadata["total_chunks"],
                "topic_shift_note": topic_shift_func,
                "entities": entities_func
            },
            template=key_points_map_template
        )
        
        key_points_combine_prompt = PromptTemplate(
            input_variables=["text"],
            partial_variables={
                "global_entities": global_entities_func
            },
            template=key_points_combine_template
        )
        
        key_points_chain = load_summarize_chain(
            llm,
            chain_type="map_reduce",
            map_prompt=key_points_map_prompt,
            combine_prompt=key_points_combine_prompt,
            verbose=True
        )
        
        return key_points_chain.run(docs)
    
    def _generate_highlights(self, llm, docs, topic_shift_func, entities_func, global_entities_func):
        """Generate highlights using map-reduce approach."""
        highlights_map_template = """
        You're analyzing part {chunk_id} of {total_chunks} of a podcast transcript.
        
        {topic_shift_note}
        
        Key entities in this section: {entities}
        
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
        
        Important entities mentioned: {global_entities}
        
        EXTRACTED QUOTES:
        {text}
        
        FINAL MEMORABLE QUOTES (one per line):
        """
        
        highlights_map_prompt = PromptTemplate(
            input_variables=["text"],
            partial_variables={
                "chunk_id": lambda x: x.metadata["chunk_id"],
                "total_chunks": lambda x: x.metadata["total_chunks"],
                "topic_shift_note": topic_shift_func,
                "entities": entities_func
            },
            template=highlights_map_template
        )
        
        highlights_combine_prompt = PromptTemplate(
            input_variables=["text"],
            partial_variables={
                "global_entities": global_entities_func
            },
            template=highlights_combine_template
        )
        
        highlights_chain = load_summarize_chain(
            llm,
            chain_type="map_reduce",
            map_prompt=highlights_map_prompt,
            combine_prompt=highlights_combine_prompt,
            verbose=True
        )
        
        return highlights_chain.run(docs)