from research_copilot.runtime.source_registry import SourceDescriptor
from .tools import WebToolkit
from .agent import WebAgent


def _available(ctx):
    return getattr(ctx.config, "ENABLE_WEB_AGENT", True)


def _toolkit(ctx):
    return WebToolkit(ctx.config)


def _agent(ctx, tools):
    return WebAgent(ctx.llm, tools)


SOURCE = SourceDescriptor(
    id="web",
    node_name="web_agent",
    is_default=True,
    is_available=_available,
    create_toolkit=_toolkit,
    create_agent=_agent,
)
