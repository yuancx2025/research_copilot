from typing import Any
from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from functools import partial

from .state import State
from .nodes import (
    analyze_chat_and_summarize,
    analyze_and_rewrite_query,
    human_input_node,
    classify_research_intent,
    aggregate_responses,
)
from .edges import route_to_agents
from research_copilot.runtime.source_registry import SourceContext

CompiledGraph = Any


def create_agent_graph(llm, config, collection=None, research_cache=None, tool_registry=None,
                       notion_service=None, retriever=None):
    """Create orchestrator graph with multi-agent routing."""
    checkpointer = InMemorySaver()
    context = SourceContext(
        llm=llm,
        config=config,
        collection=collection,
        retriever=retriever,
        extras={"notion_service": notion_service} if notion_service else {},
    )
    agent_registry = tool_registry.create_agent_graphs(context)
    print(f"✓ Agent registry created with {len(agent_registry)} agent(s)")

    print("Compiling orchestrator graph...")
    graph_builder = StateGraph(State)
    graph_builder.add_node("summarize", partial(analyze_chat_and_summarize, llm=llm))
    graph_builder.add_node("analyze_rewrite", partial(analyze_and_rewrite_query, llm=llm))
    graph_builder.add_node("human_input", human_input_node)
    graph_builder.add_node("classify_intent", partial(classify_research_intent, llm=llm))
    for agent_name, agent_subgraph in agent_registry.items():
        graph_builder.add_node(agent_name, agent_subgraph)
    graph_builder.add_node("aggregate", partial(aggregate_responses, llm=llm))

    graph_builder.add_edge(START, "summarize")
    graph_builder.add_edge("summarize", "analyze_rewrite")
    graph_builder.add_edge("human_input", "analyze_rewrite")

    def route_after_rewrite_new(state: State):
        if state.get("create_study_plan", False):
            return "aggregate"
        if not state.get("questionIsClear", False):
            return "human_input"
        return "classify_intent"

    graph_builder.add_conditional_edges("analyze_rewrite", route_after_rewrite_new)

    def route_after_classify(state: State):
        state = {**state, "available_sources": [name.removesuffix("_agent") for name in agent_registry]}
        sends = route_to_agents(state)
        if not sends:
            return "aggregate"
        return sends

    graph_builder.add_conditional_edges("classify_intent", route_after_classify)
    for agent_name in agent_registry:
        graph_builder.add_edge(agent_name, "aggregate")
    graph_builder.add_edge("aggregate", END)

    agent_graph = graph_builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_input"],
    )
    print("✓ Orchestrator graph compiled successfully.")
    return agent_graph
