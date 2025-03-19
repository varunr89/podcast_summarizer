"""
Base class for all summarizer implementations.
"""
from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any, List, Optional
import re

from ..core.logging_config import get_logger

logger = get_logger(__name__)

class BaseSummarizer(ABC):
    """Base class for all summarizer implementations."""
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    def summarize(
        self,
        transcription: str,
        custom_prompt: Optional[str] = None,
        chunk_size: int = 4000,
        chunk_overlap: int = 500,
        detail_level: str = "standard",
        temperature: float = 0.2
    ) -> Tuple[str, Dict[str, Any], List[str]]:
        """Generate a summary of the transcription."""
        pass
    
    def parse_key_points(self, key_points_text: str) -> Dict[str, str]:
        """Parse key points text into a dictionary."""
        key_points_dict = {}
        
        for line in key_points_text.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # Try to extract numbered points
            match = re.match(r'^(\d+)[\.\)]?\s+(.+)$', line)
            if match:
                number, point_text = match.groups()
                key_points_dict[number] = point_text
        
        # If no numbered points were found, create simple entries
        if not key_points_dict:
            points_list = [p.strip() for p in key_points_text.split('\n') if p.strip()]
            for i, point in enumerate(points_list, 1):
                key_points_dict[str(i)] = point
                
        return key_points_dict
    
    def parse_highlights(self, highlights_text: str) -> List[str]:
        """Parse highlights text into a list."""
        return [h.strip() for h in highlights_text.split('\n') if h.strip()]
