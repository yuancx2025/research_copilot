from typing import Dict, Any, Optional, List
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, AIMessage
from research_copilot.agents.base_agent import BaseAgent
from research_copilot.agents.prompts import get_notion_agent_prompt
from research_copilot.tools.base import SourceType
from research_copilot.tools.notion_tools import NotionToolkit
from research_copilot.core.study_plan_generator import StudyPlanGenerator
from research_copilot.utils.notion_formatter import create_notion_page_blocks
from research_copilot.orchestrator.state import State, AgentState
import logging
import asyncio
import json
import re

logger = logging.getLogger(__name__)


class NotionAgent(BaseAgent):
    """
    Agent for creating structured Notion study plans from research artifacts.
    
    Uses LLM to:
    - Generate comprehensive study plans
    - Decide on optimal structure
    - Create learning objectives, timelines, and action items
    - Format content for Notion pages
    
    This agent integrates with the orchestrator and can be invoked
    after research agents complete their work.
    """
    
    def __init__(self, llm: BaseChatModel, config):
        """
        Initialize Notion Agent.
        
        Args:
            llm: LLM instance for generating study plan content
            config: Configuration object with Notion MCP settings
        """
        toolkit = NotionToolkit(config)
        tools = toolkit.create_tools()
        # Using WEB as placeholder since Notion isn't a research source type
        super().__init__(SourceType.WEB, llm, tools)
        self.config = config
        self.toolkit = toolkit
        self.study_plan_generator = StudyPlanGenerator(llm, config)
    
    def get_system_prompt(self) -> str:
        """Return system prompt for Notion study plan creation."""
        return get_notion_agent_prompt()
    
    def _parse_tool_result_to_citation(
        self, 
        tool_name: str, 
        tool_args: dict, 
        tool_result: Any
    ) -> Optional[dict]:
        """
        Parse Notion tool results into structured citations.
        
        For Notion agent, we don't create citations from tool results
        (we create pages, not citations). This is kept for BaseAgent compatibility.
        """
        # Notion agent doesn't create citations - it creates pages
        return None
    
    def create_agent_subgraph(self):
        """
        Create custom subgraph for Notion agent that handles study plan generation.
        
        Overrides base implementation to add custom study plan creation node.
        The Notion agent doesn't need the standard agent flow - it goes directly
        to study plan generation since all research data is already in State.
        """
        from langgraph.graph import StateGraph, START, END
        from research_copilot.orchestrator.state import State
        
        # Create simple subgraph that goes directly to page creation
        # We don't need agent_node or tools since we have all data in State
        notion_agent_builder = StateGraph(State)
        notion_agent_builder.add_node("create_page_node", self._create_notion_page_node)
        
        # Go directly to page creation
        notion_agent_builder.add_edge(START, "create_page_node")
        notion_agent_builder.add_edge("create_page_node", END)
        
        return notion_agent_builder.compile()
    
    def _create_notion_page_node(self, state: State) -> Dict[str, Any]:
        """
        Node to generate study plan and create Notion page.
        Extracts research data from State and creates the Notion page.
        """
        try:
            # Extract research data from state (set by orchestrator)
            citations = state.get("citations", [])
            agent_results = state.get("agent_results", {})
            original_query = state.get("originalQuery", "")
            
            # If data not in state, try to extract from messages
            if not citations or not original_query:
                # Parse from the human message that triggered this
                for msg in reversed(state.get("messages", [])):
                    if isinstance(msg, HumanMessage):
                        content = msg.content if isinstance(msg.content, str) else str(msg.content)
                        
                        # Check if this is the study plan creation message
                        if "Create a study plan" in content or "research data" in content.lower():
                            # Extract query
                            query_match = re.search(r"Research Query: (.*?)\n", content)
                            if query_match:
                                original_query = query_match.group(1).strip()
                            
                            # Try to extract citations from JSON
                            citations_match = re.search(r"Citations \(\d+ total\):\s*(\[.*?\])", content, re.DOTALL)
                            if citations_match:
                                try:
                                    citations = json.loads(citations_match.group(1))
                                except json.JSONDecodeError:
                                    pass
                            break
            
            # Fallback: get from messages if still not found
            if not original_query:
                for msg in state.get("messages", []):
                    if isinstance(msg, HumanMessage):
                        original_query = msg.content if isinstance(msg.content, str) else str(msg.content)
                        break
            
            if not citations:
                logger.error("NotionAgent: No citations found in state or messages")
                return {
                    "messages": [AIMessage(content="❌ Notion Agent failed: No citations found. Please perform a research query first.")],
                    "notion_page_url": ""
                }
            
            if not original_query:
                original_query = "Untitled Study Plan"
            
            # Get parent page ID from config or state
            parent_page_id = getattr(self.config, 'NOTION_PARENT_PAGE_ID', None)
            if not parent_page_id:
                # Try to extract from messages
                for msg in state.get("messages", []):
                    if isinstance(msg, HumanMessage):
                        content = str(msg.content)
                        parent_match = re.search(r"Parent Page ID: (.*?)(?:\n|$)", content)
                        if parent_match:
                            parent_page_id = parent_match.group(1).strip()
                            break
            
            if not parent_page_id:
                logger.error("NotionAgent: NOTION_PARENT_PAGE_ID not configured")
                return {
                    "messages": [AIMessage(
                        content=(
                            "❌ Notion Agent failed: NOTION_PARENT_PAGE_ID not configured.\n\n"
                            "To use Notion integration, configure either:\n"
                            "  - MCP mode: USE_NOTION_MCP=true, NOTION_MCP_COMMAND, and NOTION_PARENT_PAGE_ID\n"
                            "  - Direct API mode: NOTION_API_KEY and NOTION_PARENT_PAGE_ID"
                        )
                    )],
                    "notion_page_url": ""
                }
            
            # Get answer text from state messages (from aggregate node)
            answer_text = ""
            for msg in reversed(state.get("messages", [])):
                if isinstance(msg, AIMessage) and msg.content:
                    content = msg.content if isinstance(msg.content, str) else str(msg.content)
                    # Skip if it's an error message or empty
                    if content and not content.startswith("❌") and len(content) > 10:
                        answer_text = content
                        break
            
            research_data = {
                "query": original_query,
                "citations": citations,
                "answer_text": answer_text,
                "agent_results": agent_results,
                "parent_page_id": parent_page_id
            }
            
            logger.info(f"NotionAgent: Generating study plan for query: {original_query}")
            logger.info(f"NotionAgent: Found {len(citations)} citations")
            
            # Generate study plan structure using the StudyPlanGenerator
            study_plan = self.study_plan_generator.generate_study_plan(research_data, original_query)
            
            # Convert study plan to Notion blocks
            # Use new phase-based structure if available, otherwise fall back to legacy
            notion_blocks = create_notion_page_blocks(
                overview=study_plan.get("overview", ""),
                learning_objectives=study_plan.get("learning_objectives", []),
                key_concepts=study_plan.get("key_concepts", []),
                citations=citations,
                timeline=study_plan.get("timeline", []),
                next_steps=study_plan.get("next_steps", []),
                outcome_objectives=study_plan.get("outcome_objectives"),
                phases=study_plan.get("phases")
            )
            
            logger.info(f"NotionAgent: Created {len(notion_blocks)} Notion blocks")
            
            # Create Notion page using NotionToolkit
            logger.info(f"NotionAgent: Creating page with {len(notion_blocks)} blocks")
            page_creation_result = asyncio.run(
                self.toolkit.create_study_plan_page(
                    parent_page_id=parent_page_id,
                    title=study_plan.get("title", f"Study Plan: {original_query}"),
                    content_blocks=notion_blocks
                )
            )
            
            logger.info(f"NotionAgent: Page creation result: {page_creation_result}")
            
            # Check for error more carefully
            has_error = page_creation_result and page_creation_result.get("error") is not None
            
            if page_creation_result and not has_error:
                page_url = page_creation_result.get("url") or page_creation_result.get("page_url")
                page_id = page_creation_result.get("page_id")
                
                if not page_url:
                    logger.error(f"NotionAgent: No URL in result: {page_creation_result}")
                    return {
                        "messages": [AIMessage(
                            content=(
                                "❌ Study plan creation returned success but no URL was provided.\n\n"
                                f"Response: {str(page_creation_result)[:500]}\n\n"
                                "Please check the logs for more details."
                            )
                        )],
                        "notion_page_url": ""
                    }
                
                final_answer = f"✅ Study plan created successfully! [View in Notion]({page_url})"
                if page_id:
                    final_answer += f"\n\nPage ID: `{page_id}`"
                
                logger.info(f"NotionAgent: Page created successfully: {page_url} (ID: {page_id})")
                
                return {
                    "messages": [AIMessage(content=final_answer)],
                    "notion_page_url": page_url,
                    "study_plan_data": study_plan
                }
            else:
                error_msg = page_creation_result.get("error", "Unknown error")
                details = page_creation_result.get("details", "")
                suggestion = page_creation_result.get("suggestion", "")
                server_url = page_creation_result.get("server_url", "")
                
                # Build detailed error message
                full_error = f"❌ Failed to create Notion study plan: {error_msg}"
                if details:
                    full_error += f"\n\nDetails: {details}"
                if suggestion:
                    full_error += f"\n\n{suggestion}"
                elif not suggestion and not details:
                    # Provide default suggestion if not provided
                    full_error += (
                        "\n\nTo use Notion integration, configure either:\n"
                        "  - MCP mode: USE_NOTION_MCP=true, NOTION_MCP_COMMAND, and NOTION_PARENT_PAGE_ID\n"
                        "  - Direct API mode: NOTION_API_KEY and NOTION_PARENT_PAGE_ID"
                    )
                mcp_command = getattr(self.config, 'NOTION_MCP_COMMAND', None)
                if mcp_command:
                    full_error += f"\n\nMCP Command: {' '.join(mcp_command) if isinstance(mcp_command, list) else mcp_command}"
                
                logger.error(f"NotionAgent: {full_error}")
                logger.error(f"NotionAgent: Full error response: {page_creation_result}")
                
                return {
                    "messages": [AIMessage(content=full_error)],
                    "notion_page_url": ""
                }
        except Exception as e:
            logger.error(f"Error in NotionAgent _create_notion_page_node: {e}")
            import traceback
            traceback.print_exc()
            return {
                "messages": [AIMessage(content=f"❌ An unexpected error occurred in Notion Agent: {str(e)}")],
                "notion_page_url": ""
            }

