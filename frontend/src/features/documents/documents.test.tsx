import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { DocumentsPage } from './DocumentsPage'
import { json, mockFetch, sseResponse } from '../../test/http'
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('documents', () => {
  it('validates an upload stream, updates the list, then clears it through a mutation', async () => {
    let names: string[] = []
    mockFetch({
      'GET /api/documents': () => json({ documents: names }),
      'POST /api/documents': () => { names = ['notes.md']; return sseResponse([
        { type: 'progress', fraction: 0.5, message: 'Indexing notes' },
        { type: 'result', added: 1, skipped: 0, documents: names },
      ]) },
      'DELETE /api/documents': () => { names = []; return json({ documents: names }) },
    })
    const user = userEvent.setup()
    const page = render(<QueryClientProvider client={new QueryClient()}><DocumentsPage /></QueryClientProvider>)
    await user.upload(page.container.querySelector('input[type="file"]') as HTMLInputElement,
      new File(['# Notes'], 'notes.md', { type: 'text/markdown' }))
    await user.click(screen.getByRole('button', { name: 'Add documents' }))
    expect(await screen.findByText('Indexed 1 document(s)')).toBeInTheDocument()
    expect(await screen.findByText('notes.md', { selector: 'li' })).toBeInTheDocument()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    await user.click(screen.getByRole('button', { name: 'Clear all' }))
    expect(await screen.findByText('No documents in the knowledge base yet.')).toBeInTheDocument()
  })
  it('does not treat a stream that ended without a result as successful', async () => {
    mockFetch({ 'GET /api/documents': () => json({ documents: [] }),
      'POST /api/documents': () => sseResponse([{ type: 'progress', fraction: 0.2, message: 'Started' }]) })
    const user = userEvent.setup()
    const page = render(<QueryClientProvider client={new QueryClient()}><DocumentsPage /></QueryClientProvider>)
    await user.upload(page.container.querySelector('input[type="file"]') as HTMLInputElement, new File(['# Notes'], 'notes.md'))
    await user.click(screen.getByRole('button', { name: 'Add documents' }))
    expect(await screen.findByText(/could not understand/)).toBeInTheDocument()
    expect(screen.queryByText(/Indexed 1/)).not.toBeInTheDocument()
  })
})
