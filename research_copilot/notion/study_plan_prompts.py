"""
Study plan generation prompts.

Extracted prompt functions from study_plan_generator.py for maintainability.
"""

from typing import Dict, List


def get_objectives_prompt(answer_text: str, outcome_format: bool) -> str:
    """
    Get prompt for extracting learning objectives.
    
    Args:
        answer_text: Research summary text
        outcome_format: If True, format as "I can..." statements
        
    Returns:
        Formatted prompt string
    """
    if outcome_format:
        return f"""Based on the following research summary, create 3-5 outcome-level learning objectives.
        Each objective should be a checkbox statement starting with "I can" that represents a measurable outcome.

        Research Summary:
        {answer_text[:1000]}

        Examples:
        - "I can explain transformers without notes"
        - "I can compare 5 modern architectures"
        - "I can implement a basic transformer from scratch"

        Format as a bulleted list, one objective per line. Each should start with "I can" and be specific and measurable."""
    else:
        return f"""Based on the following research summary, extract 3-5 key learning objectives.
        Each objective should be a clear, actionable statement about what someone should learn.

        Research Summary:
        {answer_text[:1000]}

        Format as a bulleted list, one objective per line. Be specific and actionable."""


def get_key_concepts_prompt(context: str) -> str:
    """
    Get prompt for extracting key concepts.
    
    Args:
        context: Research citations context
        
    Returns:
        Formatted prompt string
    """
    return f"""Based on the following research citations, extract 5-10 key concepts that someone should understand.

    Research Citations:
    {context[:1500]}

    Extract key concepts that are:
    - Important technical terms or ideas
    - Core topics covered in the research
    - Concepts that appear across multiple sources

    Format as a bulleted list, one concept per line. Be specific and use proper terminology."""


def get_atomic_units_prompt(context: str, concepts_text: str) -> str:
    """
    Get prompt for creating atomic learning units.
    
    Args:
        context: Research citations context
        concepts_text: Formatted list of key concepts
        
    Returns:
        Formatted prompt string
    """
    return f"""Based on the following research citations and key concepts, create atomic learning units.
        Each unit should be a self-contained topic that can be learned independently.

        Research Citations:
        {context[:2000]}

        Key Concepts:
        {concepts_text}

        For each concept (or group of related concepts), create a learning unit with:
        1. Topic name (the concept name)
        2. Why it matters (2-3 sentences explaining importance in plain English)
        3. Core ideas (3-5 bullet points with key ideas)
        4. Key resources (map relevant citations to this topic - include type: paper/blog/video, title, url)
        5. Optional deep dive resources (1-2 advanced resources if available)
        6. Checkpoints (2-3 self-assessment questions like "I can explain this without notes")

        Format as JSON array, one unit per concept. Limit to 8-10 units total."""


def get_phases_prompt(units_summary: str, resource_counts: Dict[str, int]) -> str:
    """
    Get prompt for grouping units into phases.
    
    Args:
        units_summary: Summary of learning units
        resource_counts: Dict with counts by resource type (arxiv, youtube, github, web)
        
    Returns:
        Formatted prompt string
    """
    arxiv_count = resource_counts.get("arxiv", 0)
    youtube_count = resource_counts.get("youtube", 0)
    github_count = resource_counts.get("github", 0)
    web_count = resource_counts.get("web", 0)
    
    return f"""Group the following learning units into logical phases (Phase 0, Phase 1, Phase 2, etc.).
        Each phase should represent a coherent learning stage with a time estimate.

        Learning Units:
        {units_summary}

        Resource Summary:
        - ArXiv papers: {arxiv_count}
        - YouTube videos: {youtube_count}
        - GitHub repos: {github_count}
        - Web articles: {web_count}

        Guidelines:
        - Phase 0: Prerequisites (foundational concepts, ½–1 day)
        - Phase 1: Core Foundations (main concepts, 2–3 days)
        - Phase 2: Advanced Topics (more complex concepts, 3–4 days)
        - Phase 3: Specialized/Current Topics (cutting-edge, 2–3 days)
        - Phase 4: Open Problems (if applicable, ongoing)

        For each phase, provide:
        - phase_number: 0, 1, 2, etc.
        - name: Phase name (e.g., "Prerequisites", "Core Foundations")
        - time_estimate: Time estimate (e.g., "½–1 day", "2–3 days")
        - topic_names: List of unit names that belong to this phase

        Format as JSON array. Create 3-5 phases total."""


def get_next_steps_prompt(objectives_text: str, resources_text: str) -> str:
    """
    Get prompt for generating next steps.
    
    Args:
        objectives_text: Formatted list of learning objectives
        resources_text: Formatted list of top resources
        
    Returns:
        Formatted prompt string
    """
    return f"""Based on the following learning objectives and top resources, create 4-6 actionable next steps.

        Learning Objectives:
        {objectives_text}

        Top Resources:
        {resources_text}

        Create specific, actionable next steps that:
        - Reference specific resources by name (truncate long titles)
        - Are concrete and achievable
        - Follow a logical learning progression
        - Include a mix of reading, watching, and hands-on activities

        Format as a bulleted list, one step per line. Start each step with an action verb (Read, Watch, Explore, Review, Practice, etc.)."""

