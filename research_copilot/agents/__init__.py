"""
Research Copilot Agents Module

This module contains all specialized research agents for the multi-agent system.
"""

from .base_agent import BaseAgent
from .local_rag_agent import LocalRAGAgent
from .arxiv_agent import ArxivAgent
from .youtube_agent import YouTubeAgent
from .github_agent import GitHubAgent
from .web_agent import WebAgent

# Import prompts module for easy access
from . import prompts

__all__ = [
    "BaseAgent",
    "LocalRAGAgent",
    "ArxivAgent",
    "YouTubeAgent",
    "GitHubAgent",
    "WebAgent",
    "prompts",
]

