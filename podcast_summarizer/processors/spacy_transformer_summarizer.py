"""
spaCy and Transformers-based summarizer for podcast transcriptions.
"""
from typing import Tuple, Dict, Any, List, Optional
import re

# Check if spaCy and transformers are available
try:
    import spacy
    import torch
    from transformers import AutoTokenizer, AutoModel
    import numpy as np
    SPACY_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SPACY_TRANSFORMERS_AVAILABLE = False

from langchain.chains.summarize import load_summarize_chain
from langchain.prompts import PromptTemplate
from langchain.schema import Document

from ..core.logging_config import get_logger
from ..core.llm_provider import get_azure_llm

logger = get_logger(__name__)

def summarize_with_spacy(
    transcription: str,
    custom_prompt: Optional[str] = None,
    chunk_size: int = 4000,
    chunk_overlap: int = 500,
    detail_level: str = "standard",
    temperature: float = 0.2
) -> Tuple[str, Dict[str, Any], List[str]]:
    """
    Generate a summary using spaCy and transformers for advanced NLP processing.
    
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
    if not SPACY_TRANSFORMERS_AVAILABLE:
        raise ImportError("spaCy and transformers are not installed. Please install them with: pip install spacy transformers torch numpy")
    
    logger.info(f"Using spaCy method with detail level: {detail_level}")
    
    # Get Azure LLM for completing the summarization
    llm = get_azure_llm(temperature=temperature)
    
    # Load spaCy model
    try:
        nlp = spacy.load("en_core_web_sm")
    except:
        # Download the model if not available
        logger.info("Downloading spaCy model en_core_web_sm")
        spacy.cli.download("en_core_web_sm")
        nlp = spacy.load("en_core_web_sm")
    
    # Process the transcript with spaCy
    logger.info("Processing transcript with spaCy")
    doc = nlp(transcription)
    
    # Extract sentences
    sentences = [sent.text for sent in doc.sents]
    logger.info(f"Extracted {len(sentences)} sentences")
    
    # Get sentence embeddings for semantic chunking
    def get_embeddings(sentences):
        """Get embeddings for a list of sentences"""
        # Use a simple transformer model
        tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
        model = AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
        
        embeddings = []
        for sentence in sentences:
            inputs = tokenizer(sentence, padding=True, truncation=True, return_tensors="pt")
            with torch.no_grad():
                outputs = model(**inputs)
            # Use mean pooling to get sentence embedding
            embeddings.append(outputs.last_hidden_state.mean(dim=1).squeeze().numpy())
        
        return np.array(embeddings)
    
    # Get embeddings
    logger.info("Generating sentence embeddings")
    embeddings = get_embeddings(sentences)
    
    # Calculate similarity between adjacent sentences
    similarities = []
    for i in range(len(embeddings) - 1):
        sim = np.dot(embeddings[i], embeddings[i+1]) / (np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[i+1]))
        similarities.append(sim)
    
    # Find potential topic shifts (points of low similarity)
    topic_shifts = []
    mean_sim = np.mean(similarities)
    std_sim = np.std(similarities)
    threshold = max(0.5, mean_sim - std_sim)  # Set reasonable threshold
    
    for i, sim in enumerate(similarities):
        if sim < threshold:
            topic_shifts.append(i + 1)  # Index of sentence after the shift
    
    logger.info(f"Detected {len(topic_shifts)} potential topic shifts")
    
    # Create context-aware chunks with topic shift information
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
    
    logger.info(f"Created {len(chunks)} context-aware chunks")
    
    # Extract entities for additional context
    entities = {}
    for ent in doc.ents:
        if ent.label_ not in entities:
            entities[ent.label_] = []
        if ent.text not in entities[ent.label_]:
            entities[ent.label_].append(ent.text)
    
    # Create LangChain documents with metadata
    docs = []
    for i, chunk in enumerate(chunks):
        # Extract entities in this chunk
        chunk_doc = nlp(chunk["text"])
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
    
    # Create summary prompt with spaCy-enhanced context
    if custom_prompt:
        map_template = custom_prompt
    else:
        if detail_level == "brief":
            map_template = """
            You're summarizing part {chunk_id} of {total_chunks} of a podcast transcript.
            
            {topic_shift_note}
            
            Key entities in this section: {entities}
            
            Write a concise summary of this section, capturing only the essential points.
            
            TRANSCRIPT SECTION:
            {text}
            
            CONCISE SECTION SUMMARY:
            """
        elif detail_level == "detailed":
            map_template = """
            You're summarizing part {chunk_id} of {total_chunks} of a podcast transcript.
            
            {topic_shift_note}
            
            Key entities in this section: {entities}
            
            Write a detailed summary of this section, capturing all significant topics,
            key points, quotes, insights, and maintaining the conversational flow.
            
            TRANSCRIPT SECTION:
            {text}
            
            DETAILED SECTION SUMMARY:
            """
        else:  # standard
            map_template = """
            You're summarizing part {chunk_id} of {total_chunks} of a podcast transcript.
            
            {topic_shift_note}
            
            Key entities in this section: {entities}
            
            Write a comprehensive summary of this section, capturing the main topics discussed,
            key points, and maintaining the context of the conversation.
            
            TRANSCRIPT SECTION:
            {text}
            
            COMPREHENSIVE SECTION SUMMARY:
            """
    
    # Create combine prompt
    if custom_prompt:
        combine_template = custom_prompt
    else:
        if detail_level == "brief":
            combine_template = """
            Create a concise 3-4 paragraph summary of this podcast by combining these section summaries.
            Focus on the most important points and maintain a cohesive narrative flow.
            
            Important entities mentioned: {global_entities}
            
            SECTION SUMMARIES:
            {text}
            
            FINAL CONCISE SUMMARY:
            """
        elif detail_level == "detailed":
            combine_template = """
            Create a detailed 6-8 paragraph summary of this podcast by combining these section summaries.
            Include all significant discussion topics, key insights, and conclusions.
            Eliminate redundancies and ensure a cohesive overall summary with a clear narrative flow.
            
            Important entities mentioned: {global_entities}
            
            SECTION SUMMARIES:
            {text}
            
            FINAL DETAILED SUMMARY:
            """
        else:  # standard
            combine_template = """
            Create a comprehensive 4-6 paragraph summary of this podcast by combining these section summaries.
            Capture the main topics discussed, key points, and important conclusions.
            Maintain a cohesive narrative flow and eliminate redundancies.
            
            Important entities mentioned: {global_entities}
            
            SECTION SUMMARIES:
            {text}
            
            FINAL COMPREHENSIVE SUMMARY:
            """
    
    # Create additional context functions
    def get_topic_shift_note(doc):
        """Get note about topic shift"""
        if doc.metadata.get("is_topic_shift", False):
            return "NOTE: This section contains a significant topic transition."
        return "This section continues the previous topic."
    
    def get_entities_text(doc):
        """Get formatted entity text"""
        entities = doc.metadata.get("entities", [])
        if entities:
            return ", ".join(entities[:5])  # Limit to 5 entities
        return "No significant entities detected"
    
    def get_global_entities(docs):
        """Get important global entities"""
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
    
    # Create map prompt
    map_prompt = PromptTemplate(
        input_variables=["text"],
        partial_variables={
            "chunk_id": lambda x: x.metadata["chunk_id"],
            "total_chunks": lambda x: x.metadata["total_chunks"],
            "topic_shift_note": get_topic_shift_note,
            "entities": get_entities_text
        },
        template=map_template
    )
    
    # Create combine prompt
    combine_prompt = PromptTemplate(
        input_variables=["text"],
        partial_variables={
            "global_entities": lambda: get_global_entities(docs)
        },
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
    
    # Generate key points with enhanced context
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
            "topic_shift_note": get_topic_shift_note,
            "entities": get_entities_text
        },
        template=key_points_map_template
    )
    
    key_points_combine_prompt = PromptTemplate(
        input_variables=["text"],
        partial_variables={
            "global_entities": lambda: get_global_entities(docs)
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
    
    key_points_text = key_points_chain.run(docs)
    
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
    
    key_points = {"points": key_points_dict}
    
    # Generate highlights with enhanced context
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
            "topic_shift_note": get_topic_shift_note,
            "entities": get_entities_text
        },
        template=highlights_map_template
    )
    
    highlights_combine_prompt = PromptTemplate(
        input_variables=["text"],
        partial_variables={
            "global_entities": lambda: get_global_entities(docs)
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
    
    highlights_text = highlights_chain.run(docs)
    highlights = [h.strip() for h in highlights_text.split('\n') if h.strip()]
    
    return summary_output, key_points, highlights