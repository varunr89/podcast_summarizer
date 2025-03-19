"""
Utility functions for text processing.
"""
from typing import List

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

def split_text(transcription: str, chunk_size: int = 4000, chunk_overlap: int = 500) -> List[Document]:
    """
    Split text into chunks with improved semantic boundary awareness.
    
    Args:
        transcription: Text to split
        chunk_size: Size of text chunks
        chunk_overlap: Overlap between chunks
        
    Returns:
        List of Document objects
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", "! ", "? ", ";", ":", " ", ""]
    )
    
    # Split into chunks
    docs = text_splitter.create_documents([transcription])
    
    # Add metadata to the documents
    for i, doc in enumerate(docs):
        doc.metadata["chunk_id"] = i + 1
        doc.metadata["total_chunks"] = len(docs)
        doc.metadata["is_first"] = i == 0
        doc.metadata["is_last"] = i == len(docs) - 1
    
    return docs

def deduplicate_highlights(highlights: List[str]) -> List[str]:
    """
    Remove duplicate or very similar highlights.
    
    Args:
        highlights: List of highlight strings
        
    Returns:
        List of unique highlights
    """
    unique_highlights = []
    
    for highlight in highlights:
        # Check if this highlight is too similar to any existing highlight
        is_unique = True
        for existing in unique_highlights:
            # Simple similarity check using word overlap
            highlight_words = set(highlight.lower().split())
            existing_words = set(existing.lower().split())
            
            if len(highlight_words) == 0 or len(existing_words) == 0:
                continue
                
            overlap_ratio = len(highlight_words & existing_words) / len(highlight_words | existing_words)
            
            if overlap_ratio > 0.6:  # 60% similarity threshold
                is_unique = False
                break
                
        if is_unique:
            unique_highlights.append(highlight)
            
    return unique_highlights
