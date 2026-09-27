"""In-process fakes for API tests: no models, vector store, or network."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from research_copilot.app.main import create_app
from research_copilot.core.research_service import ResearchService
from research_copilot.storage.export_store import ExportResult

CITATIONS = [
    {'source_type': 'arxiv', 'title': 'Attention Is All You Need', 'url': 'https://arxiv.org/abs/1706.03762',
     'snippet': 'Transformers', 'authors': ['Vaswani', 'Shazeer'], 'date': '2017-06-12', 'metadata': {}},
    {'source_type': 'youtube', 'title': 'Transcript: dQw4w9WgXcQ', 'url': 'https://youtube.com/watch?v=x',
     'metadata': {}},
    {'source_type': 'github', 'title': 'huggingface/transformers', 'url': 'https://github.com/huggingface/transformers',
     'repo': 'huggingface/transformers', 'metadata': {}},
]


class FakeChat:
    def __init__(self, events=None, gate=None):
        self.events = events if events is not None else [
            {'type': 'progress', 'node': 'prepare'},
            {'type': 'progress', 'node': 'classify_intent', 'agents': ['arxiv', 'github']},
            {'type': 'progress', 'node': 'arxiv_agent', 'source': 'arxiv'},
            {'type': 'result', 'answer': 'Transformers use attention.', 'needs_clarification': False,
             'research_data': {'citations': CITATIONS, 'agent_results': {'arxiv': [1, 2], 'github': [1]}}},
        ]
        self.gate = gate
        self.cleared = 0
        self.queries = []

    async def chat_stream(self, message):
        self.queries.append(message)
        for event in self.events:
            if self.gate is not None:
                await self.gate.wait()
            yield event

    def clear_session(self):
        self.cleared += 1


class FakeDocuments:
    def __init__(self):
        self.names = ['existing']
        self.received = []

    def list_documents(self):
        return sorted(self.names)

    def add_documents(self, paths, progress_callback=None):
        added = 0
        for i, path in enumerate(paths):
            self.received.append((Path(path).name, Path(path).read_bytes()))
            if progress_callback:
                progress_callback((i + 1) / len(paths), f'Processing {Path(path).name}')
            stem = Path(path).stem
            if stem not in self.names:
                self.names.append(stem)
                added += 1
        return added, len(paths) - added

    def clear_all(self):
        self.names = []


class FakeExporter:
    def __init__(self):
        self.published = []

    async def publish(self, draft, destination):
        self.published.append((draft, destination))
        return ExportResult(status='success', page_id='page-1', url='https://notion.so/page-1')


def make_service(backend='rest', chat=None, notion=None):
    rag = SimpleNamespace(llm=object(), tool_registry=SimpleNamespace(available_ids=lambda: ['arxiv', 'web']))
    config = SimpleNamespace(NOTION_BACKEND=backend, NOTION_PARENT_PAGE_ID='parent-page')
    return ResearchService(rag, notion, FakeExporter(), config, documents=FakeDocuments(), chat=chat or FakeChat())


def make_app(service, backend='rest', connection=None, tmp_path=None):
    config = SimpleNamespace(NOTION_BACKEND=backend, OAUTH_BASE_URL='http://127.0.0.1:7860',
                             OAUTH_TIMEOUT=300, FRONTEND_URL='', NOTION_PARENT_PAGE_ID='parent-page')
    return create_app(config, connection=connection, research_factory=lambda **_: service,
                      frontend_dir=tmp_path)


def parse_sse(text):
    events = []
    for block in text.split('\n\n'):
        data = [line[5:].strip() for line in block.splitlines() if line.startswith('data:')]
        if data:
            events.append(json.loads('\n'.join(data)))
    return events


async def settle():
    for _ in range(5):
        await asyncio.sleep(0)
