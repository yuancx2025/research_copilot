from research_copilot.runtime.source_registry import SourceDescriptor
from .tools import YouTubeToolkit
from .agent import YouTubeAgent


def _available(ctx):
    return getattr(ctx.config, "ENABLE_YOUTUBE_AGENT", True)


def _toolkit(ctx):
    return YouTubeToolkit(ctx.config)


def _agent(ctx, tools):
    return YouTubeAgent(ctx.llm, tools)


SOURCE = SourceDescriptor(
    id="youtube",
    node_name="youtube_agent",
    is_default=True,
    is_available=_available,
    create_toolkit=_toolkit,
    create_agent=_agent,
)
