import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { QueryClient } from '@tanstack/react-query'
import { followSelectedRun } from './runSubscription'
import { submitResearch } from './useResearchActions'
import { acceptEvent, useUiStore } from '../state/uiStore'
import { researchKeys } from '../queries'
import { makeDetail, makeRun } from '../../../test/fixtures'
import { json, mockFetch, sseResponse } from '../../../test/http'

const client = () => new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
beforeEach(() => { sessionStorage.clear(); useUiStore.setState({ drafts: {}, runs: {} }) })
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })

describe('research submission', () => {
  it('guards immediate duplicate submits and keeps newer composer text', async () => {
    const queryClient = client()
    queryClient.setQueryData(researchKeys.detail('c1'), makeDetail())
    useUiStore.getState().setDraft('c1', 'question')
    let resolve!: (response: Response) => void
    const calls = mockFetch({ 'POST /api/conversations/c1/runs': () => new Promise((done) => { resolve = done }) })
    const input = { conversationId: 'c1', text: 'question' }
    const first = submitResearch(queryClient, input)
    const second = submitResearch(queryClient, input)
    expect(second).toBe(first)
    useUiStore.getState().setDraft('c1', 'a newer draft')
    resolve(json(makeRun()))
    await first
    expect(calls).toHaveLength(1)
    expect(useUiStore.getState().drafts.c1).toBe('a newer draft')
    expect(queryClient.getQueryData(researchKeys.detail('c1'))).toMatchObject({ runs: [{ id: 'r1' }] })
  })
  it('reuses the request ID when retrying an ambiguous submission', async () => {
    const queryClient = client()
    const calls = mockFetch({ 'POST /api/conversations/c1/runs': [() => { throw new Error('lost response') }, () => json(makeRun())] })
    useUiStore.getState().setDraft('c1', 'question')
    const input = { conversationId: 'c1', text: 'question' }
    await expect(submitResearch(queryClient, input)).rejects.toThrow('lost response')
    expect(useUiStore.getState().drafts.c1).toBe('question')
    await submitResearch(queryClient, input)
    expect(JSON.parse(calls[0].body as string).request_id).toBe(JSON.parse(calls[1].body as string).request_id)
    expect(useUiStore.getState().drafts.c1).toBe('')
  })
  it('preserves drafts when the global backend run limit rejects a submission', async () => {
    mockFetch({ 'POST /api/conversations/c1/runs': () => json({ detail: 'Research is already running.' }, 409) })
    useUiStore.getState().setDraft('c1', 'question')
    await expect(submitResearch(client(), { conversationId: 'c1', text: 'question' })).rejects.toThrow('Another research run is active')
    expect(useUiStore.getState().drafts.c1).toBe('question')
  })
  it('submits clarification replies to the paused run and retries to the conversation', async () => {
    const queryClient = client()
    const calls = mockFetch({
      'POST /api/runs/r1/reply': () => json(makeRun()),
      'POST /api/conversations/c1/runs': () => json(makeRun({ id: 'r2', retry_of_run_id: 'r1' })),
    })
    await submitResearch(queryClient, { conversationId: 'c1', text: 'clarified', replyTo: 'r1' })
    await submitResearch(queryClient, { conversationId: 'c1', text: '', retryOf: 'r1' })
    expect(JSON.parse(calls[0].body as string)).toMatchObject({ message: 'clarified' })
    expect(JSON.parse(calls[1].body as string)).toMatchObject({ retry_of_run_id: 'r1' })
  })
})

describe('run subscriptions', () => {
  it('replays from zero on a cold view, deduplicates events and reconciles completion', async () => {
    const queryClient = client()
    const completed = makeRun({ status: 'completed', last_seq: 3 })
    queryClient.setQueryData(researchKeys.detail('c1'), makeDetail({ runs: [makeRun()] }))
    const calls = mockFetch({
      'GET /api/runs/r1/events?after=0': () => sseResponse([
        { type: 'progress', seq: 1, run_id: 'r1', node: 'prepare' },
        { type: 'progress', seq: 1, run_id: 'r1', node: 'prepare' },
        { type: 'result', seq: 3, run_id: 'r1', run: completed },
      ]),
      'GET /api/runs/r1': () => json(completed),
    })
    await followSelectedRun(queryClient, makeRun({ last_seq: 99 }), new AbortController().signal)
    expect(calls[0].url).toContain('after=0')
    expect(useUiStore.getState().runs.r1).toMatchObject({ lastSeq: 3, connection: 'settled', progress: [{ seq: 1 }] })
    expect(queryClient.getQueryData(researchKeys.detail('c1'))).toMatchObject({ runs: [{ status: 'completed' }] })
  })
  it('rejects events from another run without advancing the cursor', () => {
    expect(() => acceptEvent('r1', 'c1', { type: 'progress', run_id: 'r2', seq: 1, node: 'prepare' })).toThrow()
    expect(useUiStore.getState().runs.r1).toBeUndefined()
    expect(() => acceptEvent('r1', 'c1', { type: 'result', run_id: 'r1', seq: 1,
      run: makeRun({ conversation_id: 'c2' }) })).toThrow()
  })
  it('polls after stream loss without declaring a still-running run finished', async () => {
    vi.useFakeTimers()
    const controller = new AbortController()
    const queryClient = client()
    queryClient.setQueryData(researchKeys.detail('c1'), makeDetail({ runs: [makeRun()] }))
    mockFetch({
      'GET /api/runs/r1/events': () => { throw new Error('socket closed') },
      'GET /api/runs/r1': [() => json(makeRun()), () => json(makeRun({ status: 'completed' }))],
    })
    const pending = followSelectedRun(queryClient, makeRun(), controller.signal)
    await vi.advanceTimersByTimeAsync(0)
    expect(useUiStore.getState().runs.r1).toMatchObject({ connection: 'polling' })
    expect(queryClient.getQueryData(researchKeys.detail('c1'))).toMatchObject({ runs: [{ status: 'running' }] })
    await vi.advanceTimersByTimeAsync(2000)
    await pending
    expect(useUiStore.getState().runs.r1.connection).toBe('settled')
  })
  it('cancels fallback polling without stale updates after navigation', async () => {
    vi.useFakeTimers()
    const controller = new AbortController()
    const calls = mockFetch({
      'GET /api/runs/r1/events': () => { throw new Error('socket closed') },
      'GET /api/runs/r1': () => json(makeRun()),
    })
    const pending = followSelectedRun(client(), makeRun(), controller.signal)
    await vi.advanceTimersByTimeAsync(0)
    controller.abort()
    await pending
    await vi.advanceTimersByTimeAsync(6000)
    expect(calls.filter((call) => call.url === '/api/runs/r1')).toHaveLength(1)
  })
  it('keeps only drafts in session storage and leaves legacy snapshots untouched', async () => {
    sessionStorage.setItem('research-copilot', JSON.stringify({ messages: ['old history'] }))
    useUiStore.getState().setDraft('c1', 'unfinished')
    acceptEvent('r1', 'c1', { type: 'progress', seq: 1, run_id: 'r1', node: 'prepare' })
    expect(JSON.parse(sessionStorage.getItem('research-copilot:v2')!).state).toEqual({ drafts: { c1: 'unfinished' } })
    expect(sessionStorage.getItem('research-copilot')).toContain('old history')
  })
})
