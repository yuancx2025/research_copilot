"""Server-Sent Events responses with keepalive comments for long runs."""
import asyncio
import json
from fastapi.responses import StreamingResponse

KEEPALIVE_SECONDS = 15.0


def encode(event: dict) -> bytes:
    kind = event.get('type', 'message')
    event_id = f"id: {event['seq']}\n" if 'seq' in event else ''
    return f"{event_id}event: {kind}\ndata: {json.dumps(event, default=str)}\n\n".encode()


async def _with_keepalive(events, interval):
    iterator = events.__aiter__()
    step = None
    try:
        while True:
            if step is None:
                step = asyncio.ensure_future(iterator.__anext__())
            done, _ = await asyncio.wait({step}, timeout=interval)
            if not done:
                yield b": keepalive\n\n"
                continue
            finished, step = step, None
            try:
                event = finished.result()
            except StopAsyncIteration:
                return
            yield encode(event)
    finally:
        if step is not None:
            step.cancel()


def event_stream(events, interval=KEEPALIVE_SECONDS) -> StreamingResponse:
    return StreamingResponse(
        _with_keepalive(events, interval),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'},
    )
