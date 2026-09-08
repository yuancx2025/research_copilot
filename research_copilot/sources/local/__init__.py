from research_copilot.runtime.source_registry import SourceDescriptor
from .tools import LocalToolkit
from .agent import LocalRAGAgent


def _available(ctx):
    return getattr(ctx.config, "ENABLE_LOCAL_AGENT", True) and ctx.collection is not None


def _toolkit(ctx):
    toolkit = LocalToolkit(ctx.config, ctx.collection)
    if ctx.retriever:
        toolkit.set_retriever(ctx.retriever)
    return toolkit


def _agent(ctx, tools):
    return LocalRAGAgent(ctx.llm, tools)


SOURCE = SourceDescriptor(
    id="local",
    node_name="local_agent",
    is_default=True,
    is_available=_available,
    create_toolkit=_toolkit,
    create_agent=_agent,
)
