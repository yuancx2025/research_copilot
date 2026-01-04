"""
LLM output parsing utilities for Notion study plan generation.

Centralizes parsing logic for bullet lists, JSON arrays, and LLM calls.
"""

from typing import List, Dict, Any, Optional
from langchain_core.messages import HumanMessage
from research_copilot.core.llm_utils import extract_content_as_string
import json
import re
import logging

logger = logging.getLogger(__name__)


def parse_bullets(text: str, max_items: int = 5) -> List[str]:
    """
    Parse bullet lists from text.
    
    Handles various bullet markers: -, •, *, 1., 2., etc.
    
    Args:
        text: Text containing bulleted list
        max_items: Maximum number of items to return
        
    Returns:
        List of parsed items (strings)
    """
    items = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        
        # Remove bullet markers
        for marker in ["-", "•", "*", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "10."]:
            if line.startswith(marker):
                line = line[len(marker):].strip()
                break
        
        # Remove ALL checkbox markers ([ ] or [x]) anywhere in the line
        checkbox_pattern = r'\[\s*[xX]?\s*\]\s*'
        line = re.sub(checkbox_pattern, '', line).strip()
        
        # Remove duplicate "I can" at the start (e.g., "I can I can explain" -> "I can explain")
        if line.startswith("I can I can "):
            line = line.replace("I can I can ", "I can ", 1).strip()
        
        if line and len(line) > 2:
            items.append(line)
            if len(items) >= max_items:
                break
    
    return items


def call_llm_and_parse_list(llm, prompt: str, max_items: int = 5, fallback_func=None) -> List[str]:
    """
    Generic helper for LLM calls that return bullet lists.
    
    Args:
        llm: LLM instance
        prompt: Prompt to send to LLM
        max_items: Maximum number of items to return
        fallback_func: Optional fallback function to call on error
        
    Returns:
        Parsed list of items or result from fallback_func
    """
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        text = extract_content_as_string(response).strip()
        items = parse_bullets(text, max_items)
        return items if items else (fallback_func() if fallback_func else [])
    except Exception as e:
        logger.warning(f"LLM call failed: {e}")
        return fallback_func() if fallback_func else []


def parse_json_list(text: str) -> List[Dict[str, Any]]:
    """
    Parse JSON array from text with fallback.
    
    Tries to extract JSON array from text, handling markdown code blocks.
    Falls back to empty list if parsing fails.
    
    Args:
        text: Text that may contain JSON array
        
    Returns:
        List of dictionaries parsed from JSON array, or empty list
    """
    # First, try to extract from markdown code blocks
    code_block_pattern = r'```(?:json)?\s*(\[.*?\])\s*```'
    code_match = re.search(code_block_pattern, text, re.DOTALL)
    if code_match:
        json_str = code_match.group(1).strip()
        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
    
    # Try simple regex for JSON array (first occurrence)
    array_pattern = r'\[.*?\]'
    array_match = re.search(array_pattern, text, re.DOTALL)
    if array_match:
        json_str = array_match.group(0).strip()
        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
    
    return []


def repair_json(text: str) -> Optional[str]:
    """
    Attempt to repair malformed JSON (optional).
    
    This is a placeholder for future JSON repair logic.
    For now, returns None to indicate repair is not implemented.
    
    Args:
        text: Potentially malformed JSON text
        
    Returns:
        Repaired JSON string if successful, None otherwise
    """
    # Future: implement JSON repair logic if needed
    return None

