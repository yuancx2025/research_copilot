import asyncio
import logging
import shutil
import tempfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from research_copilot.app.contracts import stream_responses

from research_copilot.app.deps import get_research
from research_copilot.app.schemas import DocumentsOut
from research_copilot.app.security import require_csrf
from research_copilot.app.sse import event_stream

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_SUFFIXES = {'.pdf', '.md'}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024


@router.get('/documents', response_model=DocumentsOut)
async def list_documents(service=Depends(get_research)):
    return DocumentsOut(documents=await run_in_threadpool(service.list_documents))


@router.delete('/documents', response_model=DocumentsOut, dependencies=[Depends(require_csrf)])
async def clear_documents(service=Depends(get_research)):
    await run_in_threadpool(service.clear_documents)
    return DocumentsOut(documents=[])


@router.post('/documents', dependencies=[Depends(require_csrf)], response_class=StreamingResponse,
             responses=stream_responses('UploadEventOut'))
async def upload_documents(files: List[UploadFile] = File(...), service=Depends(get_research)):
    staging = Path(tempfile.mkdtemp(prefix='research-copilot-upload-'))
    paths, rejected = [], 0
    try:
        for upload in files:
            name = Path(upload.filename or '').name
            if not name or Path(name).suffix.lower() not in ALLOWED_SUFFIXES:
                rejected += 1
                continue
            target = staging / name
            size = 0
            with target.open('wb') as out:
                while chunk := await upload.read(CHUNK_BYTES):
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise HTTPException(413, f'{name} is larger than 50 MB.')
                    out.write(chunk)
            paths.append(str(target))
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return event_stream(_index(service, paths, rejected, staging))


async def _index(service, paths, rejected, staging):
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def progress(fraction, message):
        loop.call_soon_threadsafe(queue.put_nowait,
                                  {'type': 'progress', 'fraction': fraction, 'message': message})

    def work():
        try:
            return service.add_documents(paths, progress_callback=progress)
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    task = asyncio.ensure_future(asyncio.to_thread(work))
    while not task.done():
        getter = asyncio.ensure_future(queue.get())
        done, _ = await asyncio.wait({getter, task}, return_when=asyncio.FIRST_COMPLETED)
        if getter in done:
            yield getter.result()
        else:
            getter.cancel()
    while not queue.empty():
        yield queue.get_nowait()
    try:
        added, skipped = task.result()
    except Exception:
        logger.exception('Document indexing failed')
        yield {'type': 'error', 'message': 'Indexing failed. Check the server logs and retry.'}
        return
    yield {'type': 'result', 'added': added, 'skipped': skipped + rejected,
           'documents': await run_in_threadpool(service.list_documents)}
