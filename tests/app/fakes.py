"""In-process fakes for API tests: no models, vector store, or network. Records live in Postgres."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from research_copilot.app.main import create_app
from research_copilot.core.research_service import ResearchService
from research_copilot.db.repositories import ResearchRepository
from research_copilot.storage.export_store import ExportResult

CITATIONS = [
    {'source_type': 'arxiv', 'title': 'Attention Is All You Need', 'url': 'https://arxiv.org/abs/1706.03762',
     'snippet': 'Transformers', 'authors': ['Vaswani', 'Shazeer'], 'date': '2017-06-12', 'metadata': {}},
    {'source_type': 'youtube', 'title': 'Transcript: dQw4w9WgXcQ', 'url': 'https://youtube.com/watch?v=x',
     'metadata': {}},
    {'source_type': 'github', 'title': 'huggingface/transformers', 'url': 'https://github.com/huggingface/transformers',
     'repo': 'huggingface/transformers', 'metadata': {}},
]


def result_event(answer='Transformers use attention.', citations=CITATIONS, checkpoint='cp-1',
                 needs_clarification=False, agent_results=None):
    return {'type': 'result', 'answer': answer, 'needs_clarification': needs_clarification,
            'checkpoint_id': checkpoint,
            'research_data': {'citations': citations,
                              'agent_results': agent_results if agent_results is not None else {'arxiv': [1, 2], 'github': [1]}}}


DEFAULT_EVENTS = [
    {'type': 'progress', 'node': 'prepare'},
    {'type': 'progress', 'node': 'classify_intent', 'agents': ['arxiv', 'github']},
    {'type': 'progress', 'node': 'arxiv_agent', 'source': 'arxiv'},
    result_event(),
]


class FakeChat:
    """Replays scripted events. ``script`` may be a list, or a list of lists consumed per call."""

    def __init__(self, events=None, gate=None, script=None):
        self.script = list(script) if script else None
        self.events = events if events is not None else DEFAULT_EVENTS
        self.gate = gate
        self.calls = []

    @property
    def queries(self):
        return [message for message, _, _ in self.calls]

    async def chat_stream(self, message, config, resume=False):
        self.calls.append((message, config, resume))
        events = self.script.pop(0) if self.script else self.events
        for event in events:
            if self.gate is not None:
                await self.gate.wait()
            yield event


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


def fake_notion(generation='g1', connected=True, connection_id='conn-1'):
    connection = SimpleNamespace(generation=generation, connected=connected, listeners=[],
                                 record=SimpleNamespace(connection_id=connection_id))
    return SimpleNamespace(connection=connection)


def make_service(db, backend='rest', chat=None, notion=None, exporter=None):
    rag = SimpleNamespace(llm=object(), tool_registry=SimpleNamespace(available_ids=lambda: ['arxiv', 'web']))
    config = SimpleNamespace(NOTION_BACKEND=backend, NOTION_PARENT_PAGE_ID='parent-page')
    return ResearchService(rag, ResearchRepository(db), notion, exporter or FakeExporter(), config,
                           documents=FakeDocuments(), chat=chat or FakeChat())


def make_app(service, db, backend='rest', connection=None, tmp_path=None):
    config = SimpleNamespace(NOTION_BACKEND=backend, OAUTH_BASE_URL='http://127.0.0.1:7860',
                             OAUTH_TIMEOUT=300, FRONTEND_URL='', NOTION_PARENT_PAGE_ID='parent-page')
    return create_app(config, connection=connection, research_factory=lambda **_: service,
                      frontend_dir=tmp_path, database=db)


def fresh(db):
    """Another handle on the same test schema, for apps whose lifespans overlap."""
    from research_copilot.db.engine import Database
    return Database(db.url, db.schema, pool_size=2, checkpoint_pool_size=2)


def parse_sse(text):
    events = []
    for block in text.split('\n\n'):
        data = [line[5:].strip() for line in block.splitlines() if line.startswith('data:')]
        if data:
            events.append(json.loads('\n'.join(data)))
    return events


def submit(client, conversation_id, message, request_id, **extra):
    return client.post(f'/api/conversations/{conversation_id}/runs',
                       json={'message': message, 'request_id': request_id, **extra})


def run_to_end(client, conversation_id, message, request_id, **extra):
    """Submit, then follow the run's event stream until it settles. Returns (run, events)."""
    response = submit(client, conversation_id, message, request_id, **extra)
    assert response.status_code == 202, response.text
    run = response.json()
    return run, parse_sse(client.get(f"/api/runs/{run['id']}/events").text)


async def settle():
    for _ in range(5):
        await asyncio.sleep(0)
