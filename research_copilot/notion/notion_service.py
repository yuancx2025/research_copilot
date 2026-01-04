"""
Notion service for creating study plans.

Orchestrates StudyPlanGenerator, NotionRenderer, and NotionClient to create study plan pages.
This is the only place that connects generator, renderer, and client.
"""

from typing import Dict, Any
from langchain_core.messages import AIMessage
from research_copilot.notion.study_plan_generator import StudyPlanGenerator
from research_copilot.notion.notion_renderer import render_study_plan
from research_copilot.notion.notion_client import create_page
from research_copilot.core.llm_utils import extract_content_as_string
import logging

logger = logging.getLogger(__name__)


def create_notion_study_plan(
    state: Dict[str, Any],
    config,
    llm
) -> Dict[str, Any]:
    """
    Create a Notion study plan from research data in state.
    
    Clean orchestration flow:
    1. Call generator.generate_study_plan() → returns StudyPlan (with clean citations)
    2. Call renderer.render_study_plan(study_plan) → returns List[Dict] (blocks)
    3. Call client.create_page(parent_id, title, blocks) → returns page info
    
    Args:
        state: State dict with citations, agent_results, originalQuery, messages
        config: Configuration object with NOTION_API_KEY and NOTION_PARENT_PAGE_ID
        llm: LLM instance for generating study plan content
    
    Returns:
        Dict with messages and notion_page_url
    """
    # Extract research data from state
    citations = state.get("citations", [])
    agent_results = state.get("agent_results", {})
    original_query = state.get("originalQuery", "")
    
    # Get answer text from messages
    answer_text = ""
    for msg in reversed(state.get("messages", [])):
        if hasattr(msg, 'content') and msg.content:
            content = extract_content_as_string(msg.content)
            if content and not content.startswith("❌") and len(content) > 10:
                answer_text = content
                break
    
    if not original_query:
        # Try to extract from messages
        for msg in state.get("messages", []):
            if hasattr(msg, 'content') and isinstance(msg.content, str):
                original_query = msg.content
                break
    
    if not citations:
        logger.error("No citations found in state")
        return {
            "messages": [AIMessage(content="❌ Notion service failed: No citations found. Please perform a research query first.")],
            "notion_page_url": ""
        }
    
    if not original_query:
        original_query = "Untitled Study Plan"
    
    # Get parent page ID from config
    # Handle both module and dict config (LangGraph might pass state as config)
    if isinstance(config, dict):
        # Config is actually the state dict - import config module directly
        from research_copilot.config import settings as actual_config
        parent_page_id = getattr(actual_config, 'NOTION_PARENT_PAGE_ID', None)
        config = actual_config  # Use actual config for rest of function
    else:
        # Config is a module - use it directly
        parent_page_id = getattr(config, 'NOTION_PARENT_PAGE_ID', None)
    if not parent_page_id:
        logger.error("NOTION_PARENT_PAGE_ID not configured")
        return {
            "messages": [AIMessage(
                content=(
                    "❌ Notion service failed: NOTION_PARENT_PAGE_ID not configured.\n\n"
                    "To use Notion integration, configure:\n"
                    "  - NOTION_API_KEY and NOTION_PARENT_PAGE_ID"
                )
            )],
            "notion_page_url": ""
        }
    
    # Generate study plan structure using StudyPlanGenerator
    research_data = {
        "citations": citations,
        "agent_results": agent_results,
        "answer_text": answer_text
    }
    
    logger.info(f"Generating study plan for query: {original_query}")
    logger.info(f"Found {len(citations)} citations")
    
    generator = StudyPlanGenerator(llm, config)
    study_plan = generator.generate_study_plan(research_data, original_query)
    
    # Render study plan to blocks
    logger.info(f"Rendering study plan with {len(study_plan.phases)} phases")
    blocks = render_study_plan(study_plan)
    
    # Create Notion page
    logger.info(f"Creating Notion page with {len(blocks)} blocks")
    result = create_page(
        parent_page_id=parent_page_id,
        title=study_plan.title,
        children_blocks=blocks,
        config=config
    )
    
    logger.info(f"Page creation result: {result}")
    
    # Check for error
    has_error = result and result.get("error") is not None
    
    if result and not has_error:
        page_url = result.get("url") or result.get("page_url")
        page_id = result.get("page_id")
        
        if not page_url:
            logger.error(f"No URL in result: {result}")
            return {
                "messages": [AIMessage(
                    content=(
                        "❌ Study plan creation returned success but no URL was provided.\n\n"
                        f"Response: {str(result)[:500]}\n\n"
                        "Please check the logs for more details."
                    )
                )],
                "notion_page_url": ""
            }
        
        final_answer = f"✅ Study plan created successfully! [View in Notion]({page_url})"
        if page_id:
            final_answer += f"\n\nPage ID: `{page_id}`"
        
        logger.info(f"Page created successfully: {page_url} (ID: {page_id})")
        
        return {
            "messages": [AIMessage(content=final_answer)],
            "notion_page_url": page_url,
            "study_plan_data": study_plan.model_dump()  # Convert Pydantic model to dict for backward compatibility
        }
    else:
        error_msg = result.get("error", "Unknown error") if result else "No result returned"
        details = result.get("details", "") if result else ""
        
        full_error = f"❌ Failed to create Notion study plan: {error_msg}"
        if details:
            full_error += f"\n\nDetails: {details}"
        else:
            full_error += (
                "\n\nTo use Notion integration, configure:\n"
                "  - NOTION_API_KEY and NOTION_PARENT_PAGE_ID"
            )
        
        logger.error(f"Notion service error: {full_error}")
        
        return {
            "messages": [AIMessage(content=full_error)],
            "notion_page_url": ""
        }

