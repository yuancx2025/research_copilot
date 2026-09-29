import pytest

pytest.importorskip('multipart')

from fastapi.testclient import TestClient
from tests.app.fakes import make_app, make_service, parse_sse


def test_list_upload_and_clear_documents(db):
    service = make_service(db)
    with TestClient(make_app(service, db)) as client:
        assert client.get('/api/documents').json() == {'documents': ['existing']}
        response = client.post('/api/documents', files=[
            ('files', ('paper.pdf', b'%PDF-1.4', 'application/pdf')),
            ('files', ('../../escape.md', b'# notes', 'text/markdown')),
            ('files', ('existing.md', b'# dup', 'text/markdown')),
            ('files', ('image.png', b'png', 'image/png')),
        ])
        assert response.status_code == 200
        events = parse_sse(response.text)
        assert [e['type'] for e in events] == ['progress'] * 3 + ['result']
        assert events[0] == {'type': 'progress', 'fraction': pytest.approx(1 / 3), 'message': 'Processing paper.pdf'}
        assert events[-1] == {'type': 'result', 'added': 2, 'skipped': 2,
                              'documents': ['escape', 'existing', 'paper']}
        assert client.delete('/api/documents').json() == {'documents': []}

    names = [name for name, _ in service.documents.received]
    assert names == ['paper.pdf', 'escape.md', 'existing.md']
    assert service.documents.received[1][1] == b'# notes'


def test_upload_requires_files(db):
    with TestClient(make_app(make_service(db), db)) as client:
        assert client.post('/api/documents').status_code == 422
