import type { PropsWithChildren } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useNotionConnection } from './useNotionConnection'
import { notionKeys } from './queries'
import { researchKeys } from '../../research/queries'
import { studyPlanKeys } from '../../study-plan/queries'
import { json, mockFetch } from '../../../test/http'
const status = { status: 'connected', generation: 'generation-1', workspace: 'Notes', error: null, csrf: 'token' }
const setup = (client: QueryClient) => ({ children }: PropsWithChildren) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('Notion connection workflows', () => {
  it('refreshes saved plans and removes only obsolete destination searches when generation changes', async () => {
    mockFetch({ 'GET /oauth/notion/status': () => json(status) })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const view = renderHook(() => useNotionConnection(true), { wrapper: setup(client) })
    await waitFor(() => expect(view.result.current.status?.generation).toBe('generation-1'))
    client.setQueryData(researchKeys.detail('c1'), { saved: true })
    client.setQueryData(studyPlanKeys.draft('draft-1'), { saved: true })
    client.setQueryData(notionKeys.search('generation-1', 'notes'), ['old'])
    client.setQueryData(notionKeys.search('generation-2', 'notes'), ['new'])
    await act(async () => { client.setQueryData(notionKeys.status(), { ...status, generation: 'generation-2' }) })
    await waitFor(() => expect(client.getQueryData(notionKeys.search('generation-1', 'notes'))).toBeUndefined())
    expect(client.getQueryData(notionKeys.search('generation-2', 'notes'))).toEqual(['new'])
    expect(client.getQueryState(researchKeys.detail('c1'))?.isInvalidated).toBe(true)
    expect(client.getQueryState(studyPlanKeys.draft('draft-1'))?.isInvalidated).toBe(true)
  })
  it('opens the OAuth tab synchronously before the authorization request and refreshes disconnect status', async () => {
    let current = { ...status, status: 'disconnected' }
    const tab = { location: { href: '' }, close: vi.fn() }
    const open = vi.spyOn(window, 'open').mockReturnValue(tab as unknown as Window)
    const calls = mockFetch({
      'GET /oauth/notion/status': () => json(current),
      'POST /oauth/notion/start': () => { expect(open).toHaveBeenCalledOnce(); return json({ authorization_url: 'https://notion.so/authorize' }) },
      'POST /oauth/notion/disconnect': () => { current = { ...current, generation: 'generation-2' }; return json({ status: 'disconnected', message: 'Removed' }) },
    })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const view = renderHook(() => useNotionConnection(true), { wrapper: setup(client) })
    await waitFor(() => expect(view.result.current.loading).toBe(false))
    act(() => { view.result.current.connect(); expect(open).toHaveBeenCalledOnce() })
    await waitFor(() => expect(tab.location.href).toBe('https://notion.so/authorize'))
    act(() => view.result.current.disconnect())
    await waitFor(() => expect(view.result.current.status?.generation).toBe('generation-2'))
    expect(calls.filter((call) => call.url === '/oauth/notion/start')).toHaveLength(1)
  })
})
