"""
Shared LLM utilities for extracting content from LLM responses.

Handles various LLM response formats (especially Google Gemini).
Notion-specific parsing utilities are in research_copilot.notion.parsers.
"""


def extract_content_as_string(response) -> str:
    """
    Safely extract content from LLM response as a string.
    
    Handles cases where response.content might be:
    - A string (most common)
    - A list of content blocks (e.g., Google Gemini returns [{'type': 'text', 'text': '...'}])
    - A dict content block
    - A response object with .content attribute
    
    Args:
        response: LLM response object or content
        
    Returns:
        Content as a plain string
    """
    # Handle response object with .content attribute
    if hasattr(response, 'content'):
        content = response.content
    else:
        content = response
    
    return normalize_content_to_string(content)


def normalize_content_to_string(content) -> str:
    """
    Normalize any content type to a plain string.
    
    Handles:
    - Strings (returned as-is)
    - Lists of content blocks from Gemini: [{'type': 'text', 'text': '...', 'extras': {...}}]
    - Single dict content blocks
    - Other types (converted via str())
    
    Args:
        content: Content that may be string, list, or dict
        
    Returns:
        Plain string content
    """
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        # Handle list of content blocks (e.g., Google Gemini)
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                # Extract 'text' field from content block dict
                if 'text' in item:
                    text_parts.append(item['text'])
                elif 'content' in item:
                    text_parts.append(item['content'])
                else:
                    # Fallback: use str representation but this shouldn't happen
                    text_parts.append(str(item))
            elif isinstance(item, str):
                text_parts.append(item)
            elif item is not None:
                text_parts.append(str(item))
        return " ".join(text_parts)
    elif isinstance(content, dict):
        # Handle single content block dict
        if 'text' in content:
            return content['text']
        elif 'content' in content:
            return content['content']
        else:
            return str(content)
    else:
        return str(content) if content else ""
