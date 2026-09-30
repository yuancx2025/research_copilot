import type { ZodType } from 'zod'
import { zConfigOut } from './contracts/generated/zod.gen'
import { ContractError, readJson } from './validation'

export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

let csrfToken: string | null = null
export function setCsrfToken(token: string | null | undefined) {
  if (token !== undefined) csrfToken = token
}

async function refreshCsrfToken(signal?: AbortSignal | null) {
  const response = await fetch('/api/config', { credentials: 'same-origin', signal })
  if (response.ok) setCsrfToken((await readJson(response, zConfigOut, '/api/config')).csrf)
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (body && typeof body === 'object' && 'detail' in body) {
      if (typeof body.detail === 'string') return body.detail
      if (Array.isArray(body.detail)) {
        const first: unknown = body.detail[0]
        if (first && typeof first === 'object' && 'msg' in first && typeof first.msg === 'string') return first.msg
      }
    }
  } catch { /* Non-JSON errors use status text. */ }
  return response.statusText || `Request failed (${response.status})`
}

export async function apiFetch(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const method = (init.method ?? 'GET').toUpperCase()
  const headers = new Headers(init.headers)
  const writes = !['GET', 'HEAD', 'OPTIONS'].includes(method)
  if (writes && csrfToken) headers.set('X-CSRF-Token', csrfToken)
  const response = await fetch(path, { ...init, method, headers, credentials: 'same-origin' })
  if (response.status === 403 && writes && retry) {
    await refreshCsrfToken(init.signal)
    return apiFetch(path, init, false)
  }
  if (!response.ok) throw new ApiError(response.status, await errorMessage(response))
  return response
}

export async function getJson<T>(path: string, schema: ZodType<T>, signal?: AbortSignal): Promise<T> {
  return readJson(await apiFetch(path, { signal }), schema, path)
}

function jsonInit(method: string, body?: unknown): RequestInit {
  return { method, headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body) }
}

export async function sendJson<T>(path: string, method: string, schema: ZodType<T>, body?: unknown): Promise<T> {
  return readJson(await apiFetch(path, jsonInit(method, body)), schema, path)
}

export async function sendEmpty(path: string, method: string, body?: unknown): Promise<void> {
  const response = await apiFetch(path, jsonInit(method, body))
  if (response.status !== 204) throw new ContractError(path)
}
