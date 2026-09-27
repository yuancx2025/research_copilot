import { describe, expect, it } from 'vitest'
import { readEventStream } from './sse'
import { sseResponse } from '../test/http'

describe('readEventStream', () => {
  it('parses events split across chunks and skips keepalive comments', async () => {
    const events = [
      { type: 'progress', node: 'prepare' },
      { type: 'result', answer: 'multi\nline', citations: [] },
    ]
    const received: unknown[] = []
    await readEventStream(sseResponse(events, 3), (event) => received.push(event))
    expect(received).toEqual(events)
  })

  it('handles CRLF separators', async () => {
    const body = 'event: progress\r\ndata: {"type":"progress","node":"a"}\r\n\r\n'
    const received: unknown[] = []
    await readEventStream(new Response(body), (event) => received.push(event))
    expect(received).toEqual([{ type: 'progress', node: 'a' }])
  })
})
