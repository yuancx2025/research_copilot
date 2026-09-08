from research_copilot.runtime.source_registry import SourceDescriptor
from .tools import ArxivToolkit
from .agent import ArxivAgent


def _available(ctx):
    return getattr(ctx.config, "ENABLE_ARXIV_AGENT", True)


def _toolkit(ctx):
    return ArxivToolkit(ctx.config)


def _agent(ctx, tools):
    return ArxivAgent(ctx.llm, tools)


SOURCE = SourceDescriptor(
    id="arxiv",
    node_name="arxiv_agent",
    is_default=True,
    is_available=_available,
    create_toolkit=_toolkit,
    create_agent=_agent,
)
