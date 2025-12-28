"""
Notion block formatter utilities.

Converts research data and citations into Notion block format
for creating structured study plan pages.
"""

from typing import List, Dict, Any, Optional


def create_heading_block(level: int, text: str) -> Dict[str, Any]:
    """
    Create a Notion heading block.
    
    Args:
        level: Heading level (1, 2, or 3)
        text: Heading text
    
    Returns:
        Notion block dict for heading
    """
    heading_type = f"heading_{level}"
    return {
        "type": heading_type,
        heading_type: {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        }
    }


def create_paragraph_block(text: str) -> Dict[str, Any]:
    """
    Create a Notion paragraph block.
    
    Args:
        text: Paragraph text
    
    Returns:
        Notion block dict for paragraph
    """
    return {
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        }
    }


def create_bullet_list_block(items: List[str]) -> List[Dict[str, Any]]:
    """
    Create Notion bulleted list blocks.
    
    Args:
        items: List of strings for each bullet item
    
    Returns:
        List of Notion block dicts for bulleted list items
    """
    blocks = []
    for item in items:
        blocks.append({
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{"type": "text", "text": {"content": item}}]
            }
        })
    return blocks


def create_callout_block(text: str, icon: str = "💡") -> Dict[str, Any]:
    """
    Create a Notion callout block.
    
    Args:
        text: Callout text
        icon: Emoji icon (default: 💡)
    
    Returns:
        Notion block dict for callout
    """
    return {
        "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {"content": text}}],
            "icon": {"emoji": icon}
        }
    }


def create_link_block(text: str, url: str) -> Dict[str, Any]:
    """
    Create a Notion paragraph block with a link.
    
    Args:
        text: Link text
        url: Link URL
    
    Returns:
        Notion block dict for paragraph with link
    """
    return {
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{
                "type": "text",
                "text": {"content": text, "link": {"url": url}}
            }]
        }
    }


def create_divider_block() -> Dict[str, Any]:
    """
    Create a Notion divider block.
    
    Returns:
        Notion block dict for divider
    """
    return {
        "type": "divider",
        "divider": {}
    }


def create_toggle_block(title: str, children: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Create a Notion toggle (collapsible) block.
    
    Args:
        title: Toggle title
        children: List of child blocks
    
    Returns:
        Notion block dict for toggle
    """
    return {
        "type": "toggle",
        "toggle": {
            "rich_text": [{"type": "text", "text": {"content": title}}],
            "children": children
        }
    }


def create_to_do_block(text: str, checked: bool = False, children: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Create a Notion to-do block.
    
    Args:
        text: To-do item text
        checked: Whether item is checked (default: False)
        children: Optional list of child blocks (for nested content)
    
    Returns:
        Notion block dict for to-do
    """
    block = {
        "type": "to_do",
        "to_do": {
            "rich_text": [{"type": "text", "text": {"content": text}}],
            "checked": checked
        }
    }
    if children:
        block["to_do"]["children"] = children
    return block


def create_checkpoint_block(checkpoints: List[str]) -> List[Dict[str, Any]]:
    """
    Create checkpoint blocks (to-do items) for self-assessment.
    
    Args:
        checkpoints: List of checkpoint strings (e.g., "I can explain this without notes")
    
    Returns:
        List of Notion to-do block dicts
    """
    blocks = []
    blocks.append(create_heading_block(4, "Checkpoint"))
    for checkpoint in checkpoints:
        blocks.append(create_to_do_block(checkpoint, checked=False))
    return blocks


def create_learning_unit_block(unit: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Create blocks for an atomic learning unit.
    
    Args:
        unit: Dict with keys:
            - name: Topic name
            - why_it_matters: Explanation (2-3 lines)
            - core_ideas: List of core idea strings
            - key_resources: List of resource dicts with type, title, url
            - deep_dive_resources: List of advanced resource dicts
            - checkpoints: List of checkpoint strings
    
    Returns:
        List of Notion block dicts for the learning unit
    """
    blocks = []
    
    # Topic heading (H3)
    blocks.append(create_heading_block(3, unit.get("name", "Unknown Topic")))
    
    # Why it matters paragraph
    why_it_matters = unit.get("why_it_matters", "Important concept to understand.")
    blocks.append(create_paragraph_block(why_it_matters))
    
    # Core ideas bulleted list
    core_ideas = unit.get("core_ideas", [])
    if core_ideas:
        blocks.append(create_heading_block(4, "Core ideas"))
        blocks.extend(create_bullet_list_block(core_ideas))
    
    # Key resources section
    key_resources = unit.get("key_resources", [])
    if key_resources:
        blocks.append(create_heading_block(4, "Key resources"))
        for resource in key_resources:
            resource_type = resource.get("type", "web")
            title = resource.get("title", "Untitled")
            url = resource.get("url", "")
            
            if url:
                blocks.append(create_link_block(f"{title}", url))
            else:
                blocks.append(create_paragraph_block(f"{title}"))
    
    # Optional deep dive (toggle block)
    deep_dive = unit.get("deep_dive_resources", [])
    if deep_dive:
        deep_dive_blocks = []
        for resource in deep_dive:
            resource_type = resource.get("type", "web")
            title = resource.get("title", "Untitled")
            url = resource.get("url", "")
            
            if url:
                deep_dive_blocks.append(create_link_block(f"{title}", url))
            else:
                deep_dive_blocks.append(create_paragraph_block(f"{title}"))
        
        blocks.append(create_toggle_block("Optional deep dive", deep_dive_blocks))
    
    # Checkpoints
    checkpoints = unit.get("checkpoints", [])
    if checkpoints:
        blocks.extend(create_checkpoint_block(checkpoints))
    
    return blocks


def create_phase_block(phase: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Create blocks for a learning phase.
    
    Args:
        phase: Dict with keys:
            - phase_number: Phase number (0, 1, 2, etc.)
            - name: Phase name
            - time_estimate: Time estimate string (e.g., "2-3 days")
            - topics: List of atomic learning unit dicts
            - phase_checkpoint: Checkbox text (e.g., "☐ I completed Phase 0")
    
    Returns:
        List of Notion block dicts for the phase
    """
    blocks = []
    
    # Phase heading with time estimate (H2)
    phase_number = phase.get("phase_number", 0)
    phase_name = phase.get("name", f"Phase {phase_number}")
    time_estimate = phase.get("time_estimate", "")
    
    heading_text = f"Phase {phase_number}: {phase_name}"
    if time_estimate:
        heading_text += f" ({time_estimate})"
    
    blocks.append(create_heading_block(2, heading_text))
    
    # Phase-level checkbox (as separate block, not nested)
    phase_checkpoint = phase.get("phase_checkpoint", f"☐ I completed Phase {phase_number}")
    blocks.append(create_to_do_block(phase_checkpoint, checked=False))
    
    # Add topic blocks as separate blocks (not nested under checkbox)
    topics = phase.get("topics", [])
    for topic in topics:
        blocks.extend(create_learning_unit_block(topic))
    
    return blocks


def format_citation_as_notion_block(citation: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format a citation dictionary as a Notion callout block.
    
    Args:
        citation: Citation dict with title, url, source_type, etc.
    
    Returns:
        Notion block dict for citation callout
    """
    source_type = citation.get("source_type", "unknown")
    title = citation.get("title", "Untitled")
    url = citation.get("url", "")
    snippet = citation.get("snippet", "")[:200]  # Limit snippet length
    
    # Choose icon based on source type
    icons = {
        "arxiv": "📄",
        "youtube": "🎥",
        "github": "💻",
        "web": "🌐",
        "local": "📚"
    }
    icon = icons.get(source_type, "💡")
    
    # Build callout text
    callout_parts = [title]
    
    # Add authors for papers
    if source_type == "arxiv" and citation.get("authors"):
        authors = citation.get("authors", [])
        if isinstance(authors, list):
            author_str = ", ".join(authors[:3])
            if len(authors) > 3:
                author_str += " et al."
            callout_parts.append(f"\n{author_str}")
        elif isinstance(authors, str):
            callout_parts.append(f"\n{authors}")
    
    # Add channel for YouTube
    if source_type == "youtube" and citation.get("channel"):
        callout_parts.append(f"\nby {citation.get('channel')}")
    
    # Add snippet if available
    if snippet:
        callout_parts.append(f"\n{snippet}")
    
    callout_text = "\n".join(callout_parts)
    
    # Create callout block
    block = create_callout_block(callout_text, icon)
    
    # Add link if URL available
    if url:
        # For callouts with links, we need to modify the rich_text
        block["callout"]["rich_text"] = [{
            "type": "text",
            "text": {"content": title, "link": {"url": url}}
        }]
        # Add remaining text after link
        if len(callout_parts) > 1:
            remaining_text = "\n".join(callout_parts[1:])
            block["callout"]["rich_text"].append({
                "type": "text",
                "text": {"content": remaining_text}
            })
    
    return block


def format_citations_by_source(citations: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group citations by source type and format as Notion blocks.
    
    Args:
        citations: List of citation dictionaries
    
    Returns:
        Dict mapping source_type to list of Notion blocks
    """
    grouped = {}
    
    for citation in citations:
        source_type = citation.get("source_type", "unknown")
        if source_type not in grouped:
            grouped[source_type] = []
        
        block = format_citation_as_notion_block(citation)
        grouped[source_type].append(block)
    
    return grouped


def create_notion_page_blocks(
    overview: str,
    learning_objectives: List[str],
    key_concepts: List[str],
    citations: List[Dict[str, Any]],
    timeline: List[str],
    next_steps: List[str],
    outcome_objectives: Optional[List[str]] = None,
    phases: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """
    Create complete Notion page blocks for a study plan.
    
    Supports both new phase-based structure and legacy flat structure.
    
    Args:
        overview: Overview text
        learning_objectives: List of learning objective strings (legacy)
        key_concepts: List of key concept strings (legacy)
        citations: List of citation dictionaries
        timeline: List of timeline item strings (legacy)
        next_steps: List of next step strings
        outcome_objectives: Optional list of outcome-level checkbox objectives (new)
        phases: Optional list of phase dicts with topics (new)
    
    Returns:
        List of Notion block dicts for the complete page
    """
    blocks = []
    
    # Overview Section
    blocks.append(create_heading_block(2, "📋 Overview"))
    blocks.append(create_paragraph_block(overview))
    blocks.append(create_divider_block())
    
    # Use new structure if phases are provided
    if phases and outcome_objectives:
        # Outcome-level checkboxes
        blocks.append(create_heading_block(2, "🎯 Learning Outcomes"))
        for outcome in outcome_objectives:
            blocks.append(create_to_do_block(outcome, checked=False))
        blocks.append(create_divider_block())
        
        # Phases with atomic learning units
        for phase in phases:
            blocks.extend(create_phase_block(phase))
            blocks.append(create_divider_block())
        
        # Resources Section (at the end)
        blocks.append(create_heading_block(2, "📚 Additional Resources"))
        
        # Group citations by source type
        citations_by_source = format_citations_by_source(citations)
        
        source_labels = {
            "arxiv": "📄 ArXiv Papers",
            "youtube": "🎥 YouTube Videos",
            "github": "💻 GitHub Repositories",
            "web": "🌐 Web Articles",
            "local": "📚 Local Documents"
        }
        
        # Display in order: arxiv, youtube, github, web, local
        display_order = ["arxiv", "youtube", "github", "web", "local"]
        
        for source_type in display_order:
            if source_type in citations_by_source:
                # Add subheading for source type
                blocks.append(create_heading_block(3, source_labels.get(source_type, source_type.title())))
                # Add citation blocks
                blocks.extend(citations_by_source[source_type])
        
        blocks.append(create_divider_block())
        
        # Next Steps Section
        if next_steps:
            blocks.append(create_heading_block(2, "✅ Next Steps"))
            for step in next_steps:
                blocks.append(create_to_do_block(step, checked=False))
    
    else:
        # Legacy structure (backward compatibility)
        # Learning Objectives Section
        blocks.append(create_heading_block(2, "🎯 Learning Objectives"))
        blocks.extend(create_bullet_list_block(learning_objectives))
        blocks.append(create_divider_block())
        
        # Key Concepts Section
        blocks.append(create_heading_block(2, "🔑 Key Concepts"))
        blocks.extend(create_bullet_list_block(key_concepts))
        blocks.append(create_divider_block())
        
        # Resources Section
        blocks.append(create_heading_block(2, "📚 Resources"))
        
        # Group citations by source type
        citations_by_source = format_citations_by_source(citations)
        
        source_labels = {
            "arxiv": "📄 ArXiv Papers",
            "youtube": "🎥 YouTube Videos",
            "github": "💻 GitHub Repositories",
            "web": "🌐 Web Articles",
            "local": "📚 Local Documents"
        }
        
        # Display in order: arxiv, youtube, github, web, local
        display_order = ["arxiv", "youtube", "github", "web", "local"]
        
        for source_type in display_order:
            if source_type in citations_by_source:
                # Add subheading for source type
                blocks.append(create_heading_block(3, source_labels.get(source_type, source_type.title())))
                # Add citation blocks
                blocks.extend(citations_by_source[source_type])
        
        blocks.append(create_divider_block())
        
        # Timeline Section
        if timeline:
            blocks.append(create_heading_block(2, "📅 Timeline"))
            blocks.extend(create_bullet_list_block(timeline))
            blocks.append(create_divider_block())
        
        # Next Steps Section
        if next_steps:
            blocks.append(create_heading_block(2, "✅ Next Steps"))
            for step in next_steps:
                blocks.append(create_to_do_block(step, checked=False))
    
    return blocks

