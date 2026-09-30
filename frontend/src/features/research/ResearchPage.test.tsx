import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { AppConfig, ConversationDetail, Draft, Run } from '../../api/types'
import { useUiStore } from './state/uiStore'
import { json, mockFetch, sseResponse } from '../../test/http'
import { ResearchPage } from './ResearchPage'

const config: AppConfig = { notion_backend: 'rest', default_destination: 'parent-page', sources: ['arxiv'], csrf: null }

const run = (status: Run['status'], result: Run['result']): Run => ({
  id: 'r1',
  conversation_id: 'c1',
  request_id: 'request-1',
  status,
  query: 'transformers',
  retry_of_run_id: null,
  error: null,
  last_seq: status === 'completed' ? 2 : 0,
  created_at: '2026-09-28T00:00:00Z',
  finished_at: null,
  result,
})

const completed = run('completed', {
  run_id: 'r1',
  query: 'transformers',
  answer: 'Transformers rely on **attention**.',
  citations: [
    { source_type: 'arxiv', title: 'Attention Is All You Need', url: 'https://arxiv.org/abs/1706.03762', snippet: '', authors: ['Vaswani'], date: '2017', channel: null, repo: null },
  ],
  sources: { arxiv: 1 },
  needs_clarification: false,
  can_preview_plan: true,
  generation: 'rest',
})

function detail(phase: 'empty' | 'running' | 'done' | 'draft'): ConversationDetail {
  const draft: Draft = { draft_id: 'draft-1', run_id: 'r1', title: 'Transformer plan', markdown: '# Transformer plan', exportable: true }
  return {
    id: 'c1',
    title: 'transformers',
    created_at: '2026-09-28T00:00:00Z',
    updated_at: '2026-09-28T00:00:00Z',
    messages:
      phase === 'empty'
        ? []
        : [
            { id: 'm1', role: 'user', content: 'transformers', clarification: false, run_id: 'r1', request_id: 'request-1', created_at: '2026-09-28T00:00:00Z' },
            ...(phase === 'done' || phase === 'draft'
              ? [{ id: 'm2', role: 'assistant' as const, content: completed.result!.answer, clarification: false, run_id: 'r1', request_id: null, created_at: '2026-09-28T00:00:00Z' }]
              : []),
          ],
    runs: phase === 'empty' ? [] : [phase === 'running' ? run('running', null) : completed],
    drafts: phase === 'draft' ? [draft] : [],
  }
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/research/c1']}>
        <Routes>
          <Route path="/research/:conversationId?" element={<ResearchPage config={config} />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  sessionStorage.clear()
  useUiStore.setState({ drafts: {}, runs: {} })
})

afterEach(() => vi.unstubAllGlobals())

describe('ResearchPage', () => {
  it('submits a question, renders the saved answer, citations and a preview that exports', async () => {
    let phase: 'empty' | 'running' | 'done' | 'draft' = 'empty'
    const calls = mockFetch({
      'GET /api/conversations': () => json([{ id: 'c1', title: 'transformers', created_at: '2026-09-28T00:00:00Z', updated_at: '2026-09-28T00:00:00Z' }]),
      'GET /api/conversations/c1': () => json(detail(phase)),
      'POST /api/conversations/c1/runs': () => {
        phase = 'running'
        return json(run('running', null))
      },
      'GET /api/runs/r1': () => json(phase === 'running' ? run('running', null) : completed),
      'GET /api/runs/r1/events': () => {
        phase = 'done'
        return sseResponse([
          { type: 'progress', seq: 1, run_id: 'r1', node: 'classify_intent', agents: ['arxiv'] },
          { type: 'result', seq: 2, run_id: 'r1', run: completed },
        ])
      },
      'POST /api/study-plan/preview': () => {
        phase = 'draft'
        return json(detail('draft').drafts[0])
      },
      'POST /api/study-plan/export': () =>
        json({ status: 'success', page_id: 'p', url: 'https://notion.so/p', message: '', retryable: false }),
    })
    const user = userEvent.setup()
    renderPage()

    await user.type(await screen.findByRole('textbox', { name: 'Message' }), 'transformers{Enter}')

    expect(await screen.findByText('attention')).toBeInTheDocument()
    expect(within(screen.getByRole('log')).getByText('transformers')).toBeInTheDocument()
    const link = screen.getByRole('link', { name: 'Attention Is All You Need' })
    expect(link).toHaveAttribute('target', '_blank')
    expect(screen.getByText('Vaswani · 2017')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Preview study plan' }))
    expect(await screen.findByRole('heading', { name: 'Transformer plan' })).toBeInTheDocument()

    const exportButton = screen.getByRole('button', { name: 'Export displayed plan' })
    await user.click(exportButton)
    const notice = await screen.findByText(/in Notion/)
    expect(within(notice).getByRole('link')).toHaveAttribute('href', 'https://notion.so/p')
    expect(exportButton).toBeDisabled()

    const submitted = calls.find((c) => c.url === '/api/conversations/c1/runs')!
    const body = JSON.parse(submitted.body as string)
    expect(body.message).toBe('transformers')
    expect(body.request_id).toMatch(/^[0-9a-f-]{36}$/)
    const preview = calls.find((c) => c.url === '/api/study-plan/preview')!
    expect(JSON.parse(preview.body as string)).toEqual({ run_id: 'r1' })
    const exportCall = calls.find((c) => c.url === '/api/study-plan/export')!
    expect(JSON.parse(exportCall.body as string)).toEqual({ draft_id: 'draft-1', destination: 'parent-page' })
  })

  it('keeps preview disabled until research returns citations', async () => {
    mockFetch({
      'GET /api/conversations': () => json([]),
      'GET /api/conversations/c1': () => json(detail('empty')),
    })
    renderPage()
    expect(await screen.findByRole('button', { name: 'Preview study plan' })).toBeDisabled()
    expect(screen.getByText('No citations yet.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'New conversation' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Clear' })).not.toBeInTheDocument()
  })
})
