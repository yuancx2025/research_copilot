import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ResearchResult } from '../api/types'
import { json, mockFetch, sseResponse } from '../test/http'
import { clearConversation, recoverResearch, sendMessage, useResearchStore } from './researchStore'

const result: ResearchResult = {
  query: 'transformers',
  answer: 'Attention is all you need.',
  citations: [],
  sources: { arxiv: 1 },
  needs_clarification: false,
  can_preview_plan: true,
  generation: 'g1',
}

beforeEach(() => {
  useResearchStore.setState({ messages: [], result: null, draft: null, generation: undefined, pendingQuery: null, progress: [], streaming: false })
})

afterEach(() => vi.unstubAllGlobals())

describe('research store', () => {
  it('streams a question into the transcript and stores the result', async () => {
    mockFetch({
      'POST /api/research': () =>
        sseResponse([{ type: 'progress', node: 'prepare' }, { type: 'result', ...result }]),
    })
    await sendMessage('  transformers ')
    const state = useResearchStore.getState()
    expect(state.messages.map((m) => [m.role, m.content])).toEqual([
      ['user', 'transformers'],
      ['assistant', 'Attention is all you need.'],
    ])
    expect(state.result).toEqual(result)
    expect(state.pendingQuery).toBeNull()
    expect(state.streaming).toBe(false)
  })

  it('shows a rejected request as an error message', async () => {
    mockFetch({ 'POST /api/research': () => json({ detail: 'Research is already running.' }, 409) })
    await sendMessage('again')
    expect(useResearchStore.getState().messages.at(-1)).toMatchObject({
      role: 'error',
      content: 'Research is already running.',
    })
  })

  it('clears artifacts when the Notion connection generation changes', () => {
    const { syncGeneration } = useResearchStore.getState()
    syncGeneration('g1')
    useResearchStore.setState({ result, draft: { draft_id: 'd', title: 't', markdown: 'm' } })
    syncGeneration('g1')
    expect(useResearchStore.getState().result).toEqual(result)
    syncGeneration(null)
    expect(useResearchStore.getState()).toMatchObject({ result: null, draft: null, generation: null })
  })

  it('recovers a result that finished while the page was reloading', async () => {
    useResearchStore.setState({ pendingQuery: 'transformers', messages: [{ id: '1', role: 'user', content: 'transformers' }] })
    mockFetch({ 'GET /api/research/last': () => json({ running: false, result }) })
    await recoverResearch()
    const state = useResearchStore.getState()
    expect(state.messages.at(-1)).toMatchObject({ role: 'assistant', content: result.answer })
    expect(state.pendingQuery).toBeNull()
  })

  it('reattaches to a run that is still going', async () => {
    useResearchStore.setState({ pendingQuery: 'transformers' })
    mockFetch({
      'GET /api/research/last': () => json({ running: true, result: null }),
      'GET /api/research/events': () => sseResponse([{ type: 'result', ...result }]),
    })
    await recoverResearch()
    expect(useResearchStore.getState().result).toEqual(result)
  })

  it('keeps the transcript when the server refuses to reset mid-run', async () => {
    useResearchStore.setState({ messages: [{ id: '1', role: 'user', content: 'q' }] })
    mockFetch({ 'POST /api/session/reset': () => json({ detail: 'Wait for the current research to finish.' }, 409) })
    expect(await clearConversation()).toBe('Wait for the current research to finish.')
    expect(useResearchStore.getState().messages).toHaveLength(1)
  })
})
