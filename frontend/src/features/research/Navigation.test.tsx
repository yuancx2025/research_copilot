import { StrictMode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ResearchPage } from './ResearchPage'
import { useUiStore } from './state/uiStore'
import { config, makeDetail, makeRun } from '../../test/fixtures'
import { json, mockFetch, sseResponse } from '../../test/http'

function renderPage(strict = false, initial?: QueryClient) {
  const client = initial ?? new QueryClient({ defaultOptions: { queries: { retry: false, retryDelay: 0 } } })
  const page = <QueryClientProvider client={client}><MemoryRouter initialEntries={['/research/c1']}>
    <Routes><Route path="/research/:conversationId" element={<ResearchPage config={config} />} /></Routes>
  </MemoryRouter></QueryClientProvider>
  return render(strict ? <StrictMode>{page}</StrictMode> : page)
}
beforeEach(() => { useUiStore.setState({ drafts: {}, runs: {} }); sessionStorage.clear() })
afterEach(() => vi.unstubAllGlobals())

const lists = [makeDetail(), makeDetail({ id: 'c2', title: 'Second' })]
describe('conversation views', () => {
  it('detaches on navigation, scopes progress, and resumes from the last consumed sequence', async () => {
    const cancelled = vi.fn()
    const calls = mockFetch({
      'GET /api/conversations': () => json(lists),
      'GET /api/conversations/c1': () => json(makeDetail({ runs: [makeRun({ last_seq: 99 })] })),
      'GET /api/conversations/c2': () => json(makeDetail({ id: 'c2', title: 'Second' })),
      'GET /api/runs/r1/events': ({ url }) => new Response(new ReadableStream({
        start(controller) {
          if (url.endsWith('after=0')) controller.enqueue(new TextEncoder().encode('data: {"type":"progress","run_id":"r1","seq":1,"node":"prepare"}\n\n'))
        }, cancel: cancelled,
      })),
    })
    const view = renderPage()
    const user = userEvent.setup()
    await screen.findByText('Preparing sources')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Conversation' }), 'c2')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Submit' })).toBeInTheDocument())
    expect(screen.queryByText('Preparing sources')).not.toBeInTheDocument()
    await waitFor(() => expect(cancelled).toHaveBeenCalledOnce())
    await user.selectOptions(screen.getByRole('combobox', { name: 'Conversation' }), 'c1')
    await screen.findByText('Preparing sources')
    await waitFor(() => expect(calls.some((call) => call.url.endsWith('/events?after=1'))).toBe(true))
    view.unmount()
    await waitFor(() => expect(cancelled).toHaveBeenCalledTimes(2))
  })
  it.each([404, 500])('shows a load error instead of an empty conversation for HTTP %s', async (status) => {
    mockFetch({ 'GET /api/conversations': () => json(lists),
      'GET /api/conversations/c1': () => json({ detail: 'unavailable' }, status) })
    renderPage()
    expect(await screen.findByRole('button', { name: 'Reload conversation' })).toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: 'Message' })).not.toBeInTheDocument()
    expect(screen.queryByRole('log')).not.toBeInTheDocument()
  })
  it('recovers from an invalid event through an explicit reconnect at the consumed cursor', async () => {
    const cancelled = vi.fn()
    const calls = mockFetch({
      'GET /api/conversations': () => json(lists),
      'GET /api/conversations/c1': () => json(makeDetail({ runs: [makeRun()] })),
      'GET /api/runs/r1': () => json(makeRun()),
      'GET /api/runs/r1/events?after=0': () => sseResponse([
        { type: 'progress', run_id: 'r1', seq: 1, node: 'prepare' },
        { type: 'progress', run_id: 'r1', seq: 2, node: 42 },
      ]),
      'GET /api/runs/r1/events?after=1': () => new Response(new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode('data: {"type":"progress","run_id":"r1","seq":2,"node":"classify_intent"}\n\n'))
        }, cancel: cancelled,
      })),
    })
    const view = renderPage()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Reconnect progress' }))
    await waitFor(() => expect(useUiStore.getState().runs.r1).toMatchObject({ lastSeq: 2, connection: 'connected', notice: null }))
    expect(screen.getByRole('button', { name: 'Researching…' })).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Reconnect progress' })).not.toBeInTheDocument()
    expect(calls.filter((call) => call.url.includes('/events'))).toHaveLength(2)
    view.unmount()
    await waitFor(() => expect(cancelled).toHaveBeenCalledOnce())
  })
  it('releases subscriptions under Strict Mode cleanup', async () => {
    const cancelled = vi.fn()
    let opened = 0
    mockFetch({ 'GET /api/conversations': () => json(lists),
      'GET /api/conversations/c1': () => json(makeDetail({ runs: [makeRun()] })),
      'GET /api/runs/r1/events': () => {
        opened++
        return new Response(new ReadableStream<Uint8Array>({ cancel: cancelled }))
      },
    })
    const client = new QueryClient()
    client.setQueryData(['research', 'conversation', 'c1'], makeDetail({ runs: [makeRun()] }))
    const view = renderPage(true, client)
    await screen.findByRole('button', { name: 'Researching…' })
    view.unmount()
    expect(opened).toBeGreaterThanOrEqual(2)
    await waitFor(() => expect(cancelled).toHaveBeenCalledTimes(opened))
    expect(useUiStore.getState().runs.r1.notice).toBeNull()
  })
})
