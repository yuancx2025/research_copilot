from research_copilot.runtime.source_registry import SourceDescriptor
from .tools import NotionToolkit
from .agent import NotionAgent


def _available(ctx):
    service = ctx.extras.get("notion_service")
    return bool(service and service.connection.connected)


def _toolkit(ctx):
    return NotionToolkit(ctx.extras["notion_service"])


def _agent(ctx, tools):
    return NotionAgent(ctx.llm, tools)


SOURCE = SourceDescriptor(
    id="notion",
    node_name="notion_agent",
    is_default=False,
    is_available=_available,
    create_toolkit=_toolkit,
    create_agent=_agent,
)
