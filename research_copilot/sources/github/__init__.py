from research_copilot.runtime.source_registry import SourceDescriptor
from .tools import GitHubToolkit
from .agent import GitHubAgent


def _available(ctx):
    return getattr(ctx.config, "ENABLE_GITHUB_AGENT", True)


def _toolkit(ctx):
    return GitHubToolkit(ctx.config)


def _agent(ctx, tools):
    return GitHubAgent(ctx.llm, tools)


SOURCE = SourceDescriptor(
    id="github",
    node_name="github_agent",
    is_default=True,
    is_available=_available,
    create_toolkit=_toolkit,
    create_agent=_agent,
)
