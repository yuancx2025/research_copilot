import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { AppConfig } from '../../api/types'
import { useResearchStore } from '../../store/researchStore'
import { json, mockFetch, sseResponse } from '../../test/http'
import { ResearchPage } from './ResearchPage'

const config: AppConfig = { notion_backend: 'rest', default_destination: 'parent-page', sources: ['arxiv'], csrf: null }

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ResearchPage config={config} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  useResearchStore.setState({ messages: [], result: null, draft: null, generation: undefined, pendingQuery: null, progress: [], streaming: false })
})

afterEach(() => vi.unstubAllGlobals())

describe('ResearchPage', () => {
  it('submits a question, renders the answer, citations and a previewable plan that exports', async () => {
    const calls = mockFetch({
      'POST /api/research': () =>
        sseResponse([
          { type: 'progress', node: 'classify_intent', agents: ['arxiv'] },
          {
            type: 'result',
            query: 'transformers',
            answer: 'Transformers rely on **attention**.',
            citations: [
              { source_type: 'arxiv', title: 'Attention Is All You Need', url: 'https://arxiv.org/abs/1706.03762', snippet: '', authors: ['Vaswani'], date: '2017', channel: null, repo: null },
            ],
            sources: { arxiv: 1 },
            needs_clarification: false,
            can_preview_plan: true,
            generation: 'rest',
          },
        ]),
      'POST /api/study-plan/preview': () => json({ draft_id: 'draft-1', title: 'Transformer plan', markdown: '# Transformer plan' }),
      'POST /api/study-plan/export': () =>
        json({ status: 'success', page_id: 'p', url: 'https://notion.so/p', message: '', retryable: false }),
    })
    const user = userEvent.setup()
    renderPage()

    await user.type(screen.getByRole('textbox', { name: 'Message' }), 'transformers{Enter}')

    expect(await screen.findByText('attention')).toBeInTheDocument()
    expect(screen.getByText('transformers')).toBeInTheDocument()
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

    const exportCall = calls.find((c) => c.url === '/api/study-plan/export')!
    expect(JSON.parse(exportCall.body as string)).toEqual({ draft_id: 'draft-1', destination: 'parent-page' })
  })

  it('keeps preview disabled until research returns citations', () => {
    renderPage()
    expect(screen.getByRole('button', { name: 'Preview study plan' })).toBeDisabled()
    expect(screen.getByText('No citations yet.')).toBeInTheDocument()
  })
})
