import { afterEach, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppRouter } from './router'

afterEach(() => vi.unstubAllGlobals())

it('renders the standalone OAuth completion page without loading application configuration', async () => {
  const fetch = vi.fn().mockRejectedValue(new Error('Backend unavailable'))
  vi.stubGlobal('fetch', fetch)
  render(<QueryClientProvider client={new QueryClient()}>
    <MemoryRouter initialEntries={['/oauth/done']}><AppRouter /></MemoryRouter>
  </QueryClientProvider>)
  expect(await screen.findByRole('heading', { name: 'Notion connected' })).toBeInTheDocument()
  expect(fetch).not.toHaveBeenCalled()
  expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
})
