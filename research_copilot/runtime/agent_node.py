from langchain_core.messages import SystemMessage, HumanMessage
from research_copilot.runtime.agent_state import AgentState


async def agent_node(state: AgentState, llm_with_tools, system_prompt: str):
    """Run one agent turn. Callers must supply the source-specific system prompt."""
    sys_msg = SystemMessage(content=system_prompt)
    if not state.get("messages"):
        human_msg = HumanMessage(content=state["question"])
        response = await llm_with_tools.ainvoke([sys_msg] + [human_msg])
        return {"messages": [human_msg, response]}
    return {"messages": [await llm_with_tools.ainvoke([sys_msg] + state["messages"])]}
