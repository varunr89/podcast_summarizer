"""
Prompt templates for different summarization approaches.
"""
from typing import Dict, Optional

class PromptTemplates:
    """Container class for prompt templates organized by type and detail level."""
    
    @staticmethod
    def get_map_prompt(method: str, detail_level: str, custom_prompt: Optional[str] = None) -> str:
        """Get map prompt template for individual chunks."""
        if custom_prompt:
            return custom_prompt
            
        templates = {
            "brief": """
            You're summarizing part {chunk_id} of {total_chunks} of a podcast transcript.
            
            Write a concise summary of this section, capturing only the essential points.
            
            TRANSCRIPT SECTION:
            {text}
            
            CONCISE SECTION SUMMARY:
            """,
            
            "standard": """
            You're summarizing part {chunk_id} of {total_chunks} of a podcast transcript.
            
            Write a comprehensive summary of this section, capturing the main topics discussed,
            key points, and maintaining the context of the conversation.
            
            TRANSCRIPT SECTION:
            {text}
            
            COMPREHENSIVE SECTION SUMMARY:
            """,
            
            "detailed": """
            You're summarizing part {chunk_id} of {total_chunks} of a podcast transcript.
            
            Write a detailed summary of this section, capturing all significant topics,
            key points, quotes, insights, and maintaining the conversational flow.
            
            TRANSCRIPT SECTION:
            {text}
            
            DETAILED SECTION SUMMARY:
            """
        }
        
        return templates.get(detail_level, templates["standard"])
    
    @staticmethod
    def get_combine_prompt(method: str, detail_level: str, custom_prompt: Optional[str] = None) -> str:
        """Get combine prompt template for merging chunk summaries."""
        if custom_prompt:
            return custom_prompt
            
        templates = {
            "brief": """
            Create a concise 3-4 paragraph summary of this podcast by combining these section summaries.
            Focus on the most important points and maintain a cohesive narrative flow.
            Eliminate redundancies between sections.
            
            SECTION SUMMARIES:
            {text}
            
            FINAL CONCISE SUMMARY:
            """,
            
            "standard": """
            Create a comprehensive 4-6 paragraph summary of this podcast by combining these section summaries.
            Capture the main topics discussed, key points, and important conclusions.
            Maintain a cohesive narrative flow and eliminate redundancies.
            
            SECTION SUMMARIES:
            {text}
            
            FINAL COMPREHENSIVE SUMMARY:
            """,
            
            "detailed": """
            Create a detailed 6-8 paragraph summary of this podcast by combining these section summaries.
            Include all significant discussion topics, key insights, and conclusions.
            Eliminate redundancies and ensure a cohesive overall summary with a clear narrative flow.
            
            SECTION SUMMARIES:
            {text}
            
            FINAL DETAILED SUMMARY:
            """
        }
        
        return templates.get(detail_level, templates["standard"])
    
    @staticmethod
    def get_key_points_map_prompt(method: str) -> str:
        """Get key points map prompt."""
        return """
        You're analyzing part {chunk_id} of {total_chunks} of a podcast transcript.
        
        Extract 2-3 key points from this section of the transcript.
        Focus on important insights, arguments, or conclusions.
        
        TRANSCRIPT SECTION:
        {text}
        
        KEY POINTS:
        """
    
    @staticmethod
    def get_key_points_combine_prompt(method: str) -> str:
        """Get key points combine prompt."""
        return """
        From these extracted key points, create a consolidated list of 5-7 most important key points from the podcast.
        Eliminate redundancies and merge similar points.
        Number each point and provide a brief explanation for each.
        
        EXTRACTED POINTS:
        {text}
        
        FINAL KEY POINTS (numbered list):
        """
    
    @staticmethod
    def get_highlights_map_prompt(method: str) -> str:
        """Get highlights map prompt."""
        return """
        You're analyzing part {chunk_id} of {total_chunks} of a podcast transcript.
        
        Extract 1-2 memorable quotes or insights from this section that are particularly
        insightful, thought-provoking, or representative of key moments.
        
        TRANSCRIPT SECTION:
        {text}
        
        MEMORABLE QUOTES:
        """
    
    @staticmethod
    def get_highlights_combine_prompt(method: str) -> str:
        """Get highlights combine prompt."""
        return """
        From these extracted quotes and insights, select the 3-5 most memorable ones
        that best represent the key insights or moments from the podcast.
        Prioritize direct quotations when possible.
        List each quote on a separate line.
        
        EXTRACTED QUOTES:
        {text}
        
        FINAL MEMORABLE QUOTES (one per line):
        """
    
    @staticmethod
    def get_ensemble_prompt(detail_level: str, combined_summaries: str, custom_prompt: Optional[str] = None) -> str:
        """Get ensemble prompt for combining multiple summaries."""
        if custom_prompt:
            return custom_prompt + "\n\n" + combined_summaries
            
        templates = {
            "brief": f"""
            Create a concise 3-4 paragraph summary of this podcast by analyzing multiple summarization methods.
            Incorporate the best insights from each approach and resolve any contradictions.
            Focus on the most important points and maintain a cohesive narrative flow.
            
            {combined_summaries}
            
            FINAL CONCISE SUMMARY:
            """,
            
            "standard": f"""
            Create a comprehensive 4-6 paragraph summary of this podcast by analyzing multiple summarization methods.
            Incorporate the best insights from each approach and resolve any contradictions.
            Capture the main topics discussed, key points, and important conclusions.
            Maintain a cohesive narrative flow.
            
            {combined_summaries}
            
            FINAL COMPREHENSIVE SUMMARY:
            """,
            
            "detailed": f"""
            Create a detailed 6-8 paragraph summary of this podcast by analyzing multiple summarization methods.
            Incorporate the best insights from each approach and resolve any contradictions.
            Include all significant discussion topics, key insights, and conclusions.
            Ensure a cohesive overall summary with a clear narrative flow.
            
            {combined_summaries}
            
            FINAL DETAILED SUMMARY:
            """
        }
        
        return templates.get(detail_level, templates["standard"])
