import { describe, expect, it, vi } from 'vitest'
import { readEventStream } from './sse'
import { zResearchEventOut, zUploadEventOut } from './contracts/generated/zod.gen'
import { ContractError } from './validation'
import { sseResponse } from '../test/http'

describe('readEventStream', () => {
  it('parses events split across chunks and skips keepalive comments', async () => {
    const events = [{ type: 'progress', fraction: 0.5, message: 'multi\nline' },
      { type: 'result', added: 1, skipped: 0, documents: ['file.md'] }]
    const received: unknown[] = []
    await readEventStream(sseResponse(events, 3), zUploadEventOut, (event) => received.push(event))
    expect(received).toEqual(events)
  })
  it('handles CRLF separators and a trailing event without a separator', async () => {
    const body = ': keepalive\r\n\r\ndata: {"type":"error","message":"failed"}\r\n\r\ndata: {"type":"progress","fraction":1,"message":"done"}'
    const received: unknown[] = []
    await readEventStream(new Response(body), zUploadEventOut, (event) => received.push(event))
    expect(received).toHaveLength(2)
  })
  it.each([{ type: 'new-kind' }, { type: 'progress', node: 'prepare' }, { type: 'progress', seq: '1', run_id: 'r', node: 'a' }])(
    'rejects invalid research events before delivery: %j', async (event) => {
      const onEvent = vi.fn()
      await expect(readEventStream(sseResponse([event]), zResearchEventOut, onEvent)).rejects.toBeInstanceOf(ContractError)
      expect(onEvent).not.toHaveBeenCalled()
    },
  )
  it('cancels and unlocks the reader when validation fails', async () => {
    const cancel = vi.fn()
    const body = new ReadableStream({ start(controller) { controller.enqueue(new TextEncoder().encode('data: invalid\n\n')) }, cancel })
    await expect(readEventStream(new Response(body), zUploadEventOut, () => {})).rejects.toBeInstanceOf(ContractError)
    expect(cancel).toHaveBeenCalledOnce()
    expect(body.locked).toBe(false)
  })
  it('interrupts a pending read and releases the reader on navigation', async () => {
    const cancel = vi.fn()
    const body = new ReadableStream<Uint8Array>({ cancel })
    const controller = new AbortController()
    const pending = readEventStream(new Response(body), zUploadEventOut, () => {}, controller.signal)
    controller.abort()
    await expect(pending).rejects.toMatchObject({ name: 'AbortError' })
    expect(cancel).toHaveBeenCalled()
    expect(body.locked).toBe(false)
  })
})
