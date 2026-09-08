"""Register built-in sources. This is the composition root; runtime does not import sources."""
from research_copilot.runtime.source_registry import SourceRegistry
from research_copilot.sources.local import SOURCE as LOCAL
from research_copilot.sources.arxiv import SOURCE as ARXIV
from research_copilot.sources.youtube import SOURCE as YOUTUBE
from research_copilot.sources.github import SOURCE as GITHUB
from research_copilot.sources.web import SOURCE as WEB
from research_copilot.sources.notion import SOURCE as NOTION

BUILTIN_SOURCES = (LOCAL, ARXIV, YOUTUBE, GITHUB, WEB, NOTION)


def build_source_registry() -> SourceRegistry:
    registry = SourceRegistry()
    for source in BUILTIN_SOURCES:
        registry.register(source)
    return registry
