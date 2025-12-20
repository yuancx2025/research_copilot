"""
Research Copilot - A Multi-Agent Research Assistant

This package provides a sophisticated research assistant that leverages:
- Multiple specialized agents (ArXiv, YouTube, GitHub, Web, Local RAG)
- LangGraph orchestration for parallel agent execution
- Advanced RAG (Retrieval Augmented Generation) capabilities
- MCP (Model Context Protocol) for tool integration

Main Modules:
- agents: Specialized research agents for different content sources
- core: Core functionality (RAG system, document management)
- orchestrator: LangGraph-based agent coordination
- rag: Advanced retrieval and reranking
- tools: MCP and native tool implementations
- storage: Vector DB and caching infrastructure
- ui: Gradio-based user interface
- app: Main application entry points

Usage:
    # Run the Gradio UI
    python -m research_copilot.app.main
    
    # Or use the orchestrator directly
    from research_copilot.orchestrator import ResearchOrchestrator
    orchestrator = ResearchOrchestrator()
    result = await orchestrator.execute("Research quantum computing")
"""

__version__ = "0.1.0"
__author__ = "Research Copilot Team"

# Compatibility imports - allows legacy imports to work
try:
    from research_copilot.config.settings import *
except ImportError:
    pass  # Config not yet migrated

__all__ = ["__version__", "__author__"]
