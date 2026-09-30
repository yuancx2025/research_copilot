import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StudyPlanPanel } from './StudyPlanPanel'
import { exportSavedDraft } from './hooks'
import { config } from '../../test/fixtures'
import { json, mockFetch } from '../../test/http'
const draft = { draft_id: 'draft-1', run_id: 'r1', title: 'Plan', markdown: '# Plan', exportable: true }
afterEach(() => vi.unstubAllGlobals())

describe('study-plan exports', () => {
  it.each(['lost response', 'invalid response'])('locks %s outcomes through navigation', async (failure) => {
    const calls = mockFetch({ 'POST /api/study-plan/export': () => {
      if (failure === 'lost response') throw new Error('network')
      return json({ status: 'not-a-status' })
    } })
    const client = new QueryClient()
    const page = () => <QueryClientProvider client={client}><StudyPlanPanel
      config={{ ...config, notion_backend: 'rest', default_destination: 'parent-page' }} run={null} draft={draft} /></QueryClientProvider>
    const user = userEvent.setup()
    const first = render(page())
    await user.click(screen.getByRole('button', { name: 'Export displayed plan' }))
    expect(await screen.findByText(/outcome could not be confirmed/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Export displayed plan' })).toBeDisabled()
    first.unmount()
    render(page())
    expect(screen.getByRole('button', { name: 'Export displayed plan' })).toBeDisabled()
    expect(calls).toHaveLength(1)
  })
  it('guards concurrent export calls and honors pending server outcomes', async () => {
    let resolve!: (response: Response) => void
    const calls = mockFetch({ 'POST /api/study-plan/export': () => new Promise((done) => { resolve = done }) })
    const client = new QueryClient()
    const first = exportSavedDraft(client, 'draft-1', 'page')
    const second = exportSavedDraft(client, 'draft-1', 'page')
    expect(second).toBe(first)
    resolve(json({ status: 'pending', page_id: null, url: null, message: 'Already exporting.', retryable: false }))
    await first
    await exportSavedDraft(client, 'draft-1', 'page')
    expect(calls).toHaveLength(1)
  })
  it('allows retry after a definite validation rejection', async () => {
    const calls = mockFetch({ 'POST /api/study-plan/export': [
      () => json({ detail: 'Invalid destination.' }, 422),
      () => json({ status: 'success', page_id: 'page', url: 'https://notion.so/page', message: '', retryable: false }),
    ] })
    const client = new QueryClient()
    expect((await exportSavedDraft(client, 'draft-1', 'invalid')).retryable).toBe(true)
    expect((await exportSavedDraft(client, 'draft-1', 'valid')).status).toBe('success')
    expect(calls).toHaveLength(2)
  })
})
