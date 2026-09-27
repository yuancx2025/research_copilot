import { vi } from 'vitest'

export function sseResponse(events: unknown[], chunkSize = 7): Response {
  const text = events.map((e) => `event: ${(e as { type: string }).type}\ndata: ${JSON.stringify(e)}\n\n`).join(': keepalive\n\n')
  const bytes = new TextEncoder().encode(text)
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (let i = 0; i < bytes.length; i += chunkSize) controller.enqueue(bytes.slice(i, i + chunkSize))
      controller.close()
    },
  })
  return new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
}

export function json(body: unknown, status = 200): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

type Handler = (init: RequestInit & { url: string }) => Response | Promise<Response>

export function mockFetch(routes: Record<string, Handler | Handler[]>) {
  const calls: Array<{ url: string; method: string; headers: Headers; body: unknown }> = []
  const queues = new Map(Object.entries(routes).map(([key, value]) => [key, Array.isArray(value) ? [...value] : value]))
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = String(input)
    const method = (init.method ?? 'GET').toUpperCase()
    calls.push({ url, method, headers: new Headers(init.headers), body: init.body })
    const key = [`${method} ${url}`, `${method} ${url.split('?')[0]}`].find((k) => queues.has(k))
    if (!key) throw new Error(`Unexpected request ${method} ${url}`)
    const handler = queues.get(key)!
    const next = Array.isArray(handler) ? handler.length > 1 ? handler.shift()! : handler[0] : handler
    return next({ ...init, url })
  })
  vi.stubGlobal('fetch', fetchMock)
  return calls
}
