import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, getJson, sendJson, setCsrfToken } from './client'
import { json, mockFetch } from '../test/http'

afterEach(() => {
  vi.unstubAllGlobals()
  setCsrfToken(null)
})

describe('apiFetch', () => {
  it('sends the CSRF token on writes and retries once with a fresh token after 403', async () => {
    setCsrfToken('stale')
    const calls = mockFetch({
      'POST /api/session/reset': [() => json({ detail: 'Invalid CSRF token' }, 403), () => json(null, 204)],
      'GET /api/config': () => json({ csrf: 'fresh' }),
    })
    await sendJson('/api/session/reset', 'POST')
    const writes = calls.filter((c) => c.method === 'POST')
    expect(writes.map((c) => c.headers.get('X-CSRF-Token'))).toEqual(['stale', 'fresh'])
  })

  it('surfaces the backend detail message', async () => {
    mockFetch({ 'POST /api/study-plan/preview': () => json({ detail: 'Run research first.' }, 409) })
    await expect(sendJson('/api/study-plan/preview', 'POST')).rejects.toEqual(new ApiError(409, 'Run research first.'))
  })

  it('does not attach a token to reads', async () => {
    setCsrfToken('token')
    const calls = mockFetch({ 'GET /api/documents': () => json({ documents: [] }) })
    await getJson('/api/documents')
    expect(calls).toHaveLength(1)
    expect(calls[0].headers.get('X-CSRF-Token')).toBeNull()
  })
})
