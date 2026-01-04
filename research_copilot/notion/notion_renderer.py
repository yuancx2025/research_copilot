"""
Pure layout/rendering for Notion blocks.

Converts StudyPlan Pydantic models to Notion block dictionaries.
Assumes citations are already deduplicated and clean (no deduplication logic).
"""

from typing import List, Dict, Any, Optional
from research_copilot.notion.schemas import StudyPlan, Phase, LearningUnit, Citation

# Maximum text length for Notion blocks
MAX_TEXT_LENGTH = 2000


def create_heading_block(level: int, text: str) -> Dict[str, Any]:
    """Create a Notion heading block."""
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH - 3] + "..."
    
    heading_type = f"heading_{level}"
    return {
        "type": heading_type,
        heading_type: {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        }
    }


def create_paragraph_block(text: str) -> Dict[str, Any]:
    """Create a Notion paragraph block."""
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH - 3] + "..."
    
    return {
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": text}}]
        }
    }


def create_bullet_list_block(items: List[str]) -> List[Dict[str, Any]]:
    """Create Notion bulleted list blocks."""
    blocks = []
    for item in items:
        if len(item) > MAX_TEXT_LENGTH:
            item = item[:MAX_TEXT_LENGTH - 3] + "..."
        blocks.append({
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{"type": "text", "text": {"content": item}}]
            }
        })
    return blocks


def create_callout_block(text: str, icon: str = "💡") -> Dict[str, Any]:
    """Create a Notion callout block."""
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH - 3] + "..."
    
    return {
        "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {"content": text}}],
            "icon": {"emoji": icon}
        }
    }


def create_link_block(text: str, url: str) -> Dict[str, Any]:
    """Create a Notion paragraph block with a link."""
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
    """Create a Notion divider block."""
    return {
        "type": "divider",
        "divider": {}
    }


def create_toggle_block(title: str, children: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create a Notion toggle (collapsible) block."""
    return {
        "type": "toggle",
        "toggle": {
            "rich_text": [{"type": "text", "text": {"content": title}}],
            "children": children
        }
    }


def create_to_do_block(text: str, checked: bool = False, children: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Create a Notion to-do block."""
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH - 3] + "..."
    
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
    """Create checkpoint blocks (to-do items) for self-assessment."""
    blocks = []
    blocks.append(create_heading_block(4, "Checkpoint"))
    for checkpoint in checkpoints:
        blocks.append(create_to_do_block(checkpoint, checked=False))
    return blocks


def render_learning_unit(unit: LearningUnit) -> List[Dict[str, Any]]:
    """Render a learning unit as Notion blocks."""
    blocks = []
    
    blocks.append(create_heading_block(3, unit.name))
    blocks.append(create_paragraph_block(unit.why_it_matters))
    
    if unit.core_ideas:
        blocks.append(create_heading_block(4, "Core ideas"))
        blocks.extend(create_bullet_list_block(unit.core_ideas))
    
    if unit.key_resources:
        blocks.append(create_heading_block(4, "Key resources"))
        for resource in unit.key_resources:
            blocks.append(create_link_block(resource.title, resource.url) if resource.url else create_paragraph_block(resource.title))
    
    if unit.deep_dive_resources:
        deep_dive_blocks = []
        for resource in unit.deep_dive_resources:
            deep_dive_blocks.append(create_link_block(resource.title, resource.url) if resource.url else create_paragraph_block(resource.title))
        blocks.append(create_toggle_block("Optional deep dive", deep_dive_blocks))
    
    if unit.checkpoints:
        blocks.extend(create_checkpoint_block(unit.checkpoints))
    
    return blocks


def render_phase(phase: Phase) -> List[Dict[str, Any]]:
    """Render a phase as Notion blocks."""
    blocks = []
    
    phase_name = phase.name
    heading_text = f"Phase {phase.phase_number}: {phase_name}"
    if phase.time_estimate:
        heading_text += f" ({phase.time_estimate})"
    
    blocks.append(create_heading_block(2, heading_text))
    blocks.append(create_to_do_block(phase.phase_checkpoint, checked=False))
    
    for topic in phase.topics:
        blocks.extend(render_learning_unit(topic))
    
    return blocks


def render_citation(citation: Citation) -> Dict[str, Any]:
    """Format a Citation model as a Notion callout block."""
    source_type = citation.source_type
    title = citation.title
    url = citation.url
    snippet = citation.snippet[:200] if citation.snippet else ""
    
    icons = {
        "arxiv": "📄",
        "youtube": "🎥",
        "github": "💻",
        "web": "🌐",
        "local": "📚"
    }
    icon = icons.get(source_type, "💡")
    
    callout_parts = [title]
    
    # Add metadata from citation.metadata if available
    if citation.metadata:
        if source_type == "arxiv" and citation.metadata.get("authors"):
            authors = citation.metadata.get("authors", [])
            if isinstance(authors, list):
                author_str = ", ".join(authors[:3])
                if len(authors) > 3:
                    author_str += " et al."
                callout_parts.append(f"\n{author_str}")
            elif isinstance(authors, str):
                callout_parts.append(f"\n{authors}")
        
        if source_type == "youtube" and citation.metadata.get("channel"):
            callout_parts.append(f"\nby {citation.metadata.get('channel')}")
    
    if snippet:
        callout_parts.append(f"\n{snippet}")
    
    callout_text = "\n".join(callout_parts)
    block = create_callout_block(callout_text, icon)
    
    if url:
        block["callout"]["rich_text"] = [{
            "type": "text",
            "text": {"content": title, "link": {"url": url}}
        }]
        if len(callout_parts) > 1:
            remaining_text = "\n".join(callout_parts[1:])
            block["callout"]["rich_text"].append({
                "type": "text",
                "text": {"content": remaining_text}
            })
    
    return block


def render_citations_by_source(citations: List[Citation]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group citations by source type and format as Notion blocks.
    
    Assumes citations are already deduplicated and clean.
    No deduplication logic here.
    """
    grouped = {}
    
    for citation in citations:
        source_type = citation.source_type
        if source_type not in grouped:
            grouped[source_type] = []
        
        grouped[source_type].append(render_citation(citation))
    
    return grouped


def render_study_plan(plan: StudyPlan) -> List[Dict[str, Any]]:
    """
    Render a StudyPlan model as Notion blocks.
    
    Main entry point for converting StudyPlan to blocks.
    
    Args:
        plan: StudyPlan Pydantic model
        
    Returns:
        List of Notion block dictionaries
    """
    blocks = []
    
    blocks.append(create_heading_block(2, "📋 Overview"))
    blocks.append(create_paragraph_block(plan.overview))
    blocks.append(create_divider_block())
    
    if plan.phases and plan.outcome_objectives:
        blocks.append(create_heading_block(2, "🎯 Learning Outcomes"))
        for outcome in plan.outcome_objectives:
            blocks.append(create_to_do_block(outcome, checked=False))
        blocks.append(create_divider_block())
        
        for phase in plan.phases:
            blocks.extend(render_phase(phase))
            blocks.append(create_divider_block())
    else:
        # Fallback: if no phases, still show outcomes if available
        if plan.outcome_objectives:
            blocks.append(create_heading_block(2, "🎯 Learning Outcomes"))
            for outcome in plan.outcome_objectives:
                blocks.append(create_to_do_block(outcome, checked=False))
            blocks.append(create_divider_block())
    
    # Resources Section
    blocks.append(create_heading_block(2, "📚 Additional Resources"))
    citations_by_source = render_citations_by_source(plan.citations)
    
    source_labels = {
        "arxiv": "📄 ArXiv Papers",
        "youtube": "🎥 YouTube Videos",
        "github": "💻 GitHub Repositories",
        "web": "🌐 Web Articles",
        "local": "📚 Local Documents"
    }
    
    display_order = ["arxiv", "youtube", "github", "web", "local"]
    for source_type in display_order:
        if source_type in citations_by_source:
            blocks.append(create_heading_block(3, source_labels.get(source_type, source_type.title())))
            blocks.extend(citations_by_source[source_type])
    
    blocks.append(create_divider_block())
    
    # Next Steps Section
    if plan.next_steps:
        blocks.append(create_heading_block(2, "✅ Next Steps"))
        for step in plan.next_steps:
            blocks.append(create_to_do_block(step, checked=False))
    
    return blocks

