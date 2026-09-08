"""Build source agents the same way production does: toolkit once, then tools."""
from research_copilot.sources.local.tools import LocalToolkit
from research_copilot.sources.local.agent import LocalRAGAgent
from research_copilot.sources.arxiv.tools import ArxivToolkit
from research_copilot.sources.arxiv.agent import ArxivAgent
from research_copilot.sources.youtube.tools import YouTubeToolkit
from research_copilot.sources.youtube.agent import YouTubeAgent
from research_copilot.sources.github.tools import GitHubToolkit
from research_copilot.sources.github.agent import GitHubAgent
from research_copilot.sources.web.tools import WebToolkit
from research_copilot.sources.web.agent import WebAgent


def local_agent(llm, collection, config):
    return LocalRAGAgent(llm, LocalToolkit(config, collection).create_tools())


def arxiv_agent(llm, config):
    return ArxivAgent(llm, ArxivToolkit(config).create_tools())


def youtube_agent(llm, config):
    return YouTubeAgent(llm, YouTubeToolkit(config).create_tools())


def github_agent(llm, config):
    return GitHubAgent(llm, GitHubToolkit(config).create_tools())


def web_agent(llm, config):
    return WebAgent(llm, WebToolkit(config).create_tools())
