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
        """
        Prompt for extracting actionable, quote‑grounded takeaways from one chunk.
        (Function name retained for backward compatibility.)
        """
        return """
        You're analyzing part {chunk_id} of {total_chunks} of a podcast transcript.

        Identify 1‑2 practical takeaways—specific actions, habits, or mindsets—that a listener
        could apply in their own life based ONLY on this section.
        • Each takeaway MUST be supported by 1‑2 brief direct quotes from this section.  
        • Do NOT invent advice; if no actionable takeaway exists, return: "NO PRACTICAL TAKEAWAY".

        TRANSCRIPT SECTION:
        {text}

        PRACTICAL TAKEAWAYS:
        e.g. "1": "**Schedule reflection time** — Block a 30‑minute slot each week to assess goals. 
        Quote: "If you don't make space to think, your calendar will fill itself." 
        """

    @staticmethod
    def get_key_points_combine_prompt(method: str) -> str:
        """
        Prompt for merging chunk‑level takeaways into a final actionable list.
        (Function name retained for backward compatibility.)
        """
        return """
        From these chunk‑level takeaways, create a consolidated list of 3‑5 distinct, 
        practical takeaways grounded in the podcast. 
        • Merge duplicates and eliminate redundancies.  
        • Number each takeaway.  
        • After each takeaway include at least one supporting quote from the speaker.  
        • Do NOT fabricate advice or quotes.

        EXTRACTED TAKEAWAYS:
        {text}

        FINAL PRACTICAL TAKEAWAYS (numbered list):
        e.g. "1": "**Schedule reflection time** — Block a 30‑minute slot each week to assess goals. 
        Quote: "If you don't make space to think, your calendar will fill itself."
        e.g. "2": "**Embrace small experiments** — Test new ideas on a small scale before committing. 
        Quote: "Treat every change like a tiny experiment you can learn from."
        """
    
    @staticmethod
    def get_highlights_map_prompt(method: str) -> str:
        """Prompt for extracting memorable quotes from one chunk."""
        return """
        You're analyzing part {chunk_id} of {total_chunks} of a podcast transcript.

        Extract the 1‑2 most memorable DIRECT quotes from this section.
        • Quotes must be copied verbatim (no paraphrasing or fabrication).  
        • Return ONLY a numbered list of quotes, e.g.  
          1. "First quote."  
          2. "Second quote."

        Do NOT add any other text.

        TRANSCRIPT SECTION:
        {text}

        NUMBERED QUOTES:
        """

    @staticmethod
    def get_highlights_combine_prompt(method: str) -> str:
        """Prompt for consolidating memorable quotes."""
        return """
        From the quotes below, select the 5‑10 most memorable DIRECT quotes that best
        capture the key insights or moments of the podcast.
        • Preserve exact wording (no paraphrasing or fabrication).  
        • Return ONLY a numbered list of quotes, one per line, e.g.  
          1. "Quote one."  
          2. "Quote two."

        Do NOT add any other text.

        EXTRACTED QUOTES:
        {text}

        FINAL NUMBERED QUOTES:
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
