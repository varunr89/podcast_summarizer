from typing import List, Dict, Any, Tuple
from ..api.common import logger
import json
import re

def sanitize_point_text(text: str) -> str:
    """
    Remove existing numbering or bullet points from the start of a string.
    """
    text = text.strip()
    # Remove patterns like "1.", "2)", "-", "*", etc. from beginning
    return re.sub(r"^(\s*[\d\-\*\•]+\s*[\.\)]\s*|\s*[\-\*\•]\s*)", "", text)

def strip_markdown_formatting(text: str) -> str:
    """
    Removes common markdown formatting like bold, italics, code blocks, and inline links.
    """
    text = text.strip()

    # Remove bold (**text** or __text__)
    text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)

    # Remove italics (*text* or _text_)
    text = re.sub(r"(\*|_)(.*?)\1", r"\2", text)

    # Remove inline code: `code`
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Remove links but keep the link text: [text](url)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    return text


def format_points(points: List[str]) -> List[str]:
    """
    Format a list of bullet points consistently using markdown "- ".
    Strips existing bullets, numbers, and markdown formatting.
    """
    formatted = []
    for point in points:
        clean = sanitize_point_text(point)
        clean = strip_markdown_formatting(clean)
        if clean:
            formatted.append(f"- {clean}")
    return formatted

def parse_flexible_json(raw_value):
    """
    Parses a value that might be:
    - A proper list or dict ✅
    - A JSON string of a list or dict ✅
    - A malformed or irrelevant string ❌
    Returns: a parsed list or dict, or [] if unparseable.
    """
    if isinstance(raw_value, (list, dict)):
        return raw_value

    if isinstance(raw_value, str):
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, (list, dict)):
                return parsed
        except json.JSONDecodeError:
            pass  # fallback below

    return []

def format_email_content(content: List[Dict[str, Any]], 
                         failed_summaries: List[Tuple[str, str]]) -> str:
    """
    Format the email content with summaries and highlights.
    Preserves existing formatting while ensuring clean layout.
    
    Args:
        content: List of episode summaries with title, summary, key_points, highlights
        failed_summaries: List of (episode_title, failure_reason) tuples
        
    Returns:
        str: Formatted email body
    """
    logger.debug(f"Formatting email content for {len(content)} episodes")

    lines = ["# Your Podcast Episode Summaries", ""]

    for item in content:
        title = item.get("title", "Unknown Episode")
        summary = item.get("summary", "").strip()

        key_points_raw = item.get('key_points', [])
        key_points_parsed = parse_flexible_json(key_points_raw)
        key_points = list(key_points_parsed.values()) if isinstance(key_points_parsed, dict) else key_points_parsed

        highlights_raw = item.get('highlights', [])
        highlights_parsed = parse_flexible_json(highlights_raw)
        highlights = highlights_parsed if isinstance(highlights_parsed, list) else []

        lines.extend([
            "---",
            f"## {title}",
            "",
            summary,
            ""
        ])

        if key_points:
            lines.append("### 🔑 Key Points")
            lines.extend(format_points(key_points))
            lines.append("")

        if highlights:
            lines.append("### ✨ Highlights")
            lines.extend(format_points(highlights))
            lines.append("")

    if failed_summaries:
        lines.extend([
            "---",
            "## ❌ Failed Summaries",
            ""
        ])
        for title, reason in failed_summaries:
            lines.append(f"- **{title}**: {reason}")
        lines.append("")

    return "\n".join(lines)