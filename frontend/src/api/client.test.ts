import { afterEach, describe, expect, it } from 'vitest'
import { vi } from 'vitest'
import { ApiError, getJson, sendJson, sendEmpty, setCsrfToken } from './client'
import { ContractError } from './validation'
import { zConfigOut, zDocumentsOut, zDraftOut, zRunOut } from './contracts/generated/zod.gen'
import { json, mockFetch } from '../test/http'
import { config, makeRun } from '../test/fixtures'

afterEach(() => { vi.unstubAllGlobals(); setCsrfToken(null) })

describe('validated HTTP requests', () => {
  it('refreshes CSRF once and preserves the original write body', async () => {
    setCsrfToken('stale')
    const calls = mockFetch({
      'DELETE /test': [() => json({ detail: 'Invalid CSRF token' }, 403), () => json(null, 204)],
      'GET /api/config': () => json({ notion_backend: 'mcp', default_destination: '', sources: [], csrf: 'fresh' }),
    })
    await sendEmpty('/test', 'DELETE', { request_id: 'same-request' })
    const writes = calls.filter((call) => call.method === 'DELETE')
    expect(writes.map((call) => call.headers.get('X-CSRF-Token'))).toEqual(['stale', 'fresh'])
    expect(writes[0].body).toEqual(writes[1].body)
  })
  it('surfaces the backend detail message without retrying', async () => {
    const calls = mockFetch({ 'POST /preview': () => json({ detail: 'Run research first.' }, 409) })
    await expect(sendJson('/preview', 'POST', zDraftOut)).rejects.toEqual(new ApiError(409, 'Run research first.'))
    expect(calls).toHaveLength(1)
  })
  it('passes read cancellation and does not attach CSRF to reads', async () => {
    setCsrfToken('token')
    const signal = new AbortController().signal
    const calls = mockFetch({ 'GET /documents': (init) => {
      expect(init.signal).toBe(signal)
      return json({ documents: [] })
    } })
    await getJson('/documents', zDocumentsOut, signal)
    expect(calls[0].headers.get('X-CSRF-Token')).toBeNull()
  })
  it.each([{ documents: 'wrong' }, {}, null])('rejects malformed JSON shapes: %j', async (payload) => {
    mockFetch({ 'GET /documents': () => json(payload) })
    await expect(getJson('/documents', zDocumentsOut)).rejects.toBeInstanceOf(ContractError)
  })
  it('rejects invalid JSON and unexpected empty responses', async () => {
    mockFetch({ 'GET /bad': () => new Response('not json'), 'POST /empty': () => json(null, 204) })
    await expect(getJson('/bad', zDocumentsOut)).rejects.toBeInstanceOf(ContractError)
    await expect(sendJson('/empty', 'POST', zDocumentsOut)).rejects.toBeInstanceOf(ContractError)
  })
  it('accepts nullable fields, documented defaults, extra fields and timezone offsets', async () => {
    mockFetch({ 'GET /run': () => json({
      id: 'r', conversation_id: 'c', request_id: 'request-1', query: 'test', status: 'running',
      created_at: '2026-09-29T10:00:00-04:00', finished_at: null, result: null, extra: 'ignored',
    }) })
    const run = await getJson('/run', zRunOut)
    expect(run.created_at).toBe('2026-09-29T10:00:00-04:00')
    expect(run.result).toBeNull()
    expect(run.last_seq).toBe(0)
    expect(run).not.toHaveProperty('extra')
  })
  it('rejects unknown run statuses and invalid refreshed config', async () => {
    expect(zRunOut.safeParse({ ...makeRun(), status: 'complete' }).success).toBe(false)
    expect(zConfigOut.safeParse({ ...config, csrf: 1 }).success).toBe(false)
  })
})
