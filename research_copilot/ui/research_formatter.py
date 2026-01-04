"""
Utility functions for formatting research artifacts for display in Gradio UI.
"""
from typing import List, Dict, Any


def format_citations_by_source(citations: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group citations by source type.
    
    Args:
        citations: List of citation dictionaries
        
    Returns:
        Dictionary mapping source types to lists of citations
    """
    grouped = {}
    
    for citation in citations:
        source_type = citation.get("source_type", "unknown")
        if source_type not in grouped:
            grouped[source_type] = []
        grouped[source_type].append(citation)
    
    return grouped


def format_citation_display(citation: Dict[str, Any]) -> str:
    """
    Format a single citation for display.
    
    Args:
        citation: Citation dictionary
        
    Returns:
        Formatted string representation
    """
    title = citation.get("title", "Untitled")
    url = citation.get("url", "")
    source_type = citation.get("source_type", "unknown")
    
    # Format based on source type
    if source_type == "arxiv":
        authors = citation.get("authors", "")
        published = citation.get("published", "")
        arxiv_id = citation.get("arxiv_id", "")
        
        parts = [f"**{title}**"]
        if authors:
            parts.append(f"by {authors}")
        if published:
            parts.append(f"({published})")
        if arxiv_id:
            parts.append(f"[ArXiv: {arxiv_id}]({url})")
        elif url:
            parts.append(f"[Link]({url})")
            
    elif source_type == "youtube":
        channel = citation.get("channel", "")
        published = citation.get("published_at", "")
        
        parts = [f"**{title}**"]
        if channel:
            parts.append(f"by {channel}")
        if published:
            parts.append(f"({published})")
        if url:
            parts.append(f"[Watch Video]({url})")
            
    elif source_type == "github":
        repo_name = citation.get("repo_name", "")
        description = citation.get("description", "")
        
        parts = [f"**{title or repo_name}**"]
        if description:
            parts.append(f"- {description[:100]}...")
        if url:
            parts.append(f"[View Repo]({url})")
            
    elif source_type == "web":
        parts = [f"**{title}**"]
        if url:
            parts.append(f"[Read Article]({url})")
            
    else:
        # Generic format
        parts = [f"**{title}**"]
        if url:
            parts.append(f"[Link]({url})")
    
    return " | ".join(parts)


def format_citations_markdown(citations: List[Dict[str, Any]]) -> str:
    """
    Format all citations as markdown grouped by source type.
    
    Args:
        citations: List of citation dictionaries
    
    Returns:
        Markdown formatted string
    """
    if not citations:
        return "No citations available."
    
    # Filter out citations with non-human-readable titles (e.g., "Transcript: VIDEO_ID")
    filtered_citations = []
    for citation in citations:
        title = citation.get("title", "").strip()
        source_type = citation.get("source_type", "")
        
        # Skip YouTube citations with transcript IDs or video IDs as titles
        if source_type == "youtube":
            title_lower = title.lower()
            # Skip if title is just "Transcript: VIDEO_ID" or just a video ID
            if (title_lower.startswith("transcript:") or 
                (len(title) <= 15 and title.replace("_", "").replace("-", "").isalnum())):
                continue
        
        filtered_citations.append(citation)
    
    if not filtered_citations:
        return "No citations available."
    
    grouped = format_citations_by_source(filtered_citations)
    
    markdown_parts = []
    
    # Source type labels
    source_labels = {
        "arxiv": "📄 ArXiv Papers",
        "youtube": "🎥 YouTube Videos",
        "github": "💻 GitHub Repositories",
        "web": "🌐 Web Articles",
        "local": "📚 Local Documents",
        "unknown": "📋 Other Sources"
    }
    
    # Display in order: arxiv, youtube, github, web, local, unknown
    display_order = ["arxiv", "youtube", "github", "web", "local", "unknown"]
    
    for source_type in display_order:
        if source_type in grouped:
            label = source_labels.get(source_type, f"📋 {source_type.title()}")
            markdown_parts.append(f"### {label}")
            markdown_parts.append("")
            
            for citation in grouped[source_type]:
                formatted = format_citation_display(citation)
                markdown_parts.append(f"- {formatted}")
            
            markdown_parts.append("")
    
    return "\n".join(markdown_parts)


def format_agent_results_summary(agent_results: Dict[str, List[Dict[str, Any]]]) -> str:
    """
    Create a summary of agent results.
    
    Args:
        agent_results: Dictionary mapping agent types to their results
        
    Returns:
        Markdown formatted summary
    """
    if not agent_results:
        return "No results from agents."
    
    parts = ["### Research Sources Used", ""]
    
    source_labels = {
        "arxiv": "📄 ArXiv",
        "youtube": "🎥 YouTube",
        "github": "💻 GitHub",
        "web": "🌐 Web",
        "local": "📚 Local Documents"
    }
    
    for source_type, results in agent_results.items():
        label = source_labels.get(source_type, source_type.title())
        count = len(results)
        parts.append(f"- **{label}**: {count} result{'s' if count != 1 else ''}")
    
    return "\n".join(parts)
