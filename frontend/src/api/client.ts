export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// Kept in memory only; the backend rotates it whenever the server restarts.
let csrfToken: string | null = null

export function setCsrfToken(token: string | null | undefined) {
  if (token !== undefined) csrfToken = token
}

async function refreshCsrfToken() {
  const response = await fetch('/api/config', { credentials: 'same-origin' })
  if (response.ok) setCsrfToken((await response.json()).csrf)
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail) && body.detail[0]?.msg) return body.detail[0].msg
  } catch {
    // Non-JSON error bodies fall through to the status text.
  }
  return response.statusText || `Request failed (${response.status})`
}

export async function apiFetch(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const method = (init.method ?? 'GET').toUpperCase()
  const headers = new Headers(init.headers)
  const writes = !['GET', 'HEAD', 'OPTIONS'].includes(method)
  if (writes && csrfToken) headers.set('X-CSRF-Token', csrfToken)
  const response = await fetch(path, { ...init, method, headers, credentials: 'same-origin' })
  if (response.status === 403 && writes && retry) {
    await refreshCsrfToken()
    return apiFetch(path, init, false)
  }
  if (!response.ok) throw new ApiError(response.status, await errorMessage(response))
  return response
}

export async function getJson<T>(path: string): Promise<T> {
  return (await apiFetch(path)).json()
}

export async function sendJson<T>(path: string, method: string, body?: unknown): Promise<T> {
  const response = await apiFetch(path, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  return response.status === 204 ? (undefined as T) : response.json()
}
