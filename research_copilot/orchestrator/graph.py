from typing import Dict, Any, Optional
from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import ToolNode, tools_condition
from functools import partial
from langchain_core.language_models import BaseChatModel

from .state import State, AgentState
from .nodes import *
from .edges import *

# Agent registry imports
from research_copilot.agents.local_rag_agent import LocalRAGAgent
from research_copilot.agents.arxiv_agent import ArxivAgent
from research_copilot.agents.youtube_agent import YouTubeAgent
from research_copilot.agents.github_agent import GitHubAgent
from research_copilot.agents.web_agent import WebAgent
from research_copilot.notion.notion_service import create_notion_study_plan

# CompiledGraph is the return type of StateGraph.compile()
CompiledGraph = Any


def create_agent_registry(llm: BaseChatModel, config, collection=None) -> Dict[str, CompiledGraph]:
    """
    Creates and returns all specialized agent subgraphs.
    
    Returns dict mapping agent names to compiled subgraphs:
    {
        "local_agent": <CompiledGraph>,
        "arxiv_agent": <CompiledGraph>,
        "youtube_agent": <CompiledGraph>,
        "github_agent": <CompiledGraph>,
        "web_agent": <CompiledGraph>
    }
    
    Args:
        llm: LLM instance to use for all agents
        config: Configuration object (may contain agent enablement flags)
        collection: Vector store collection (required for LocalRAGAgent)
    
    Returns:
        Dictionary mapping agent names to compiled subgraphs
    """
    registry = {}
    
    # Check config flags if they exist (with defaults to True for backward compatibility)
    enable_arxiv = getattr(config, 'ENABLE_ARXIV_AGENT', True)
    enable_youtube = getattr(config, 'ENABLE_YOUTUBE_AGENT', True)
    enable_github = getattr(config, 'ENABLE_GITHUB_AGENT', True)
    enable_web = getattr(config, 'ENABLE_WEB_AGENT', True)
    enable_local = getattr(config, 'ENABLE_LOCAL_AGENT', True)
    
    # Create Local RAG Agent (always available if collection provided)
    if enable_local and collection is not None:
        try:
            local_agent = LocalRAGAgent(llm, collection, config)
            registry["local_agent"] = local_agent.create_agent_subgraph()
            print("✓ Local RAG agent initialized")
        except Exception as e:
            print(f"⚠ Warning: Failed to initialize Local RAG agent: {e}")
    
    # Create ArXiv Agent
    if enable_arxiv:
        try:
            arxiv_agent = ArxivAgent(llm, config)
            registry["arxiv_agent"] = arxiv_agent.create_agent_subgraph()
            print("✓ ArXiv agent initialized")
        except Exception as e:
            print(f"⚠ Warning: Failed to initialize ArXiv agent: {e}")
    
    # Create YouTube Agent
    if enable_youtube:
        try:
            youtube_agent = YouTubeAgent(llm, config)
            registry["youtube_agent"] = youtube_agent.create_agent_subgraph()
            print("✓ YouTube agent initialized")
        except Exception as e:
            print(f"⚠ Warning: Failed to initialize YouTube agent: {e}")
    
    # Create GitHub Agent
    if enable_github:
        try:
            github_agent = GitHubAgent(llm, config)
            registry["github_agent"] = github_agent.create_agent_subgraph()
            print("✓ GitHub agent initialized")
        except Exception as e:
            print(f"⚠ Warning: Failed to initialize GitHub agent: {e}")
    
    # Create Web Agent
    if enable_web:
        try:
            web_agent = WebAgent(llm, config)
            registry["web_agent"] = web_agent.create_agent_subgraph()
            print("✓ Web agent initialized")
        except Exception as e:
            print(f"⚠ Warning: Failed to initialize Web agent: {e}")
    
    # Notion service is handled separately in graph creation, not as an agent
    
    if not registry:
        raise RuntimeError("No agents could be initialized. Check configuration and dependencies.")
    
    print(f"✓ Agent registry created with {len(registry)} agent(s)")
    return registry


def create_agent_graph(llm, config, collection=None, research_cache=None):
    """
    Create orchestrator graph with multi-agent routing.
    
    Args:
        llm: LLM instance
        config: Configuration object
        collection: Vector store collection (for LocalRAGAgent)
        research_cache: Optional ResearchCache instance for session caching
    
    Returns:
        Compiled orchestrator graph
    """
    checkpointer = InMemorySaver()
    
    # Create agent registry
    agent_registry = create_agent_registry(llm, config, collection)
    
    print("Compiling orchestrator graph...")
    graph_builder = StateGraph(State)
    
    # Core nodes
    graph_builder.add_node("summarize", partial(analyze_chat_and_summarize, llm=llm))
    graph_builder.add_node("analyze_rewrite", partial(analyze_and_rewrite_query, llm=llm))
    graph_builder.add_node("human_input", human_input_node)
    
    # New orchestrator nodes
    graph_builder.add_node("classify_intent", partial(classify_research_intent, llm=llm))
    
    # Add agent nodes from registry
    for agent_name, agent_subgraph in agent_registry.items():
        graph_builder.add_node(agent_name, agent_subgraph)
    
    # Aggregation node
    graph_builder.add_node("aggregate", partial(aggregate_responses, llm=llm))
    
    # Notion service node (if configured)
    notion_api_key = getattr(config, 'NOTION_API_KEY', None)
    notion_parent_page_id = getattr(config, 'NOTION_PARENT_PAGE_ID', None)
    enable_notion = notion_api_key and notion_parent_page_id
    
    if enable_notion:
        graph_builder.add_node(
            "create_notion_plan",
            partial(create_notion_study_plan, config=config, llm=llm)
        )
    
    # Wire up edges
    graph_builder.add_edge(START, "summarize")
    graph_builder.add_edge("summarize", "analyze_rewrite")
    graph_builder.add_edge("human_input", "analyze_rewrite")
    
    # Route after rewrite: if clear, go to classify_intent; else, human_input
    # Special case: if create_study_plan=True, skip to aggregate directly
    def route_after_rewrite_new(state: State):
        # If creating study plan, skip analysis and go directly to aggregate
        if state.get("create_study_plan", False):
            return "aggregate"
        if not state.get("questionIsClear", False):
            return "human_input"
        else:
            return "classify_intent"
    
    graph_builder.add_conditional_edges("analyze_rewrite", route_after_rewrite_new)
    
    # New orchestrator flow: classify_intent → route_to_agents (returns Send objects) → [agents] → aggregate
    # route_to_agents returns Send objects, which LangGraph uses to route to agent nodes
    # Handle case where route_to_agents returns empty list (create_study_plan=True)
    def route_after_classify(state: State):
        """Route after classify_intent - handle both research agents and study plan creation."""
        sends = route_to_agents(state)
        if not sends:
            # No research agents to invoke (create_study_plan=True), go directly to aggregate
            return "aggregate"
        # Return sends for research agents (LangGraph will handle parallel execution)
        return sends
    
    graph_builder.add_conditional_edges("classify_intent", route_after_classify)
    
    # All research agent nodes route to aggregate
    for agent_name in agent_registry.keys():
        graph_builder.add_edge(agent_name, "aggregate")
    
    # Route after aggregate: check if study plan creation is requested
    def route_after_aggregate(state: State):
        """Route to Notion service if study plan creation is requested."""
        if state.get("create_study_plan", False) and enable_notion:
            return "create_notion_plan"
        return END
    
    graph_builder.add_conditional_edges("aggregate", route_after_aggregate)
    
    # Notion service routes to END
    if enable_notion:
        graph_builder.add_edge("create_notion_plan", END)
    
    agent_graph = graph_builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_input"]
    )
    
    print("✓ Orchestrator graph compiled successfully.")
    return agent_graph
