import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { QueryClient } from '@tanstack/react-query'
import type { Run } from '../api/types'
import { json, mockFetch, sseResponse } from '../test/http'
import { followSavedRun, sendMessage, takeEvent, useUiStore } from './researchStore'

const run: Run = {
  id: 'r1',
  conversation_id: 'c1',
  request_id: 'request-1',
  status: 'running',
  query: 'transformers',
  retry_of_run_id: null,
  error: null,
  last_seq: 0,
  created_at: '',
  finished_at: null,
  result: null,
}

beforeEach(() => {
  sessionStorage.clear()
  useUiStore.setState({ drafts: {}, streamingRunId: null, progress: [], streamNotice: null })
})

afterEach(() => vi.unstubAllGlobals())

describe('research store', () => {
  it('ignores a replayed event sequence', () => {
    const seen = new Set<number>()
    expect(takeEvent(seen, { seq: 1 })).toBe(true)
    expect(takeEvent(seen, { seq: 1 })).toBe(false)
    expect(takeEvent(seen, { seq: 2 })).toBe(true)
  })

  it('leaves the legacy browser snapshot untouched', () => {
    sessionStorage.setItem('research-copilot', JSON.stringify({ state: { messages: [{ id: 'old', content: 'secret' }] } }))
    expect(useUiStore.persist.getOptions().name).toBe('research-copilot:v2')
    expect(useUiStore.getState().drafts).toEqual({})
    expect(sessionStorage.getItem('research-copilot')).toContain('secret')
  })

  it('submits once and reconciles the saved transcript', async () => {
    const calls = mockFetch({
      'POST /api/conversations/c1/runs': () => json({ ...run, last_seq: 0 }),
      'GET /api/runs/r1/events?after=0': () =>
        sseResponse([
          { type: 'progress', seq: 1, run_id: 'r1', node: 'prepare' },
          { type: 'progress', seq: 1, run_id: 'r1', node: 'prepare' },
          { type: 'result', seq: 2, run_id: 'r1', run: { ...run, status: 'completed', result: null } },
        ]),
      'GET /api/conversations/c1': () => json({ id: 'c1', messages: [], runs: [], drafts: [] }),
    })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    await sendMessage(client, 'c1', '  transformers ')
    const submitted = calls.filter((call) => call.url === '/api/conversations/c1/runs')
    expect(submitted).toHaveLength(1)
    expect(JSON.parse(submitted[0].body as string).message).toBe('transformers')
    expect(useUiStore.getState().streamingRunId).toBeNull()
  })

  it('treats a lost stream as a connection problem until the run settles', async () => {
    mockFetch({
      'GET /api/runs/r1/events?after=0': () => {
        throw new Error('socket closed')
      },
      'GET /api/runs/r1': () => json({ ...run, status: 'running' }),
    })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    await followSavedRun(client, run)
    expect(useUiStore.getState().streamNotice).toBe('The progress stream disconnected. Research is still running.')
    expect(useUiStore.getState().streamingRunId).toBeNull()
  })
})
