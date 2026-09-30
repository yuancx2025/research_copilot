import type { ZodType } from 'zod'
import { ContractError, validate } from './validation'

function parseBlock<T>(block: string, schema: ZodType<T>): T | null {
  const data = block.split(/\r?\n/).filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).replace(/^ /, ''))
  if (!data.length) return null
  let payload: unknown
  try { payload = JSON.parse(data.join('\n')) } catch { throw new ContractError('event stream') }
  return validate(schema, payload, 'event stream')
}

// Framing is shared; callers provide the schema for their own event protocol.
export async function readEventStream<T>(
  response: Response, schema: ZodType<T>, onEvent: (event: T) => void, signal?: AbortSignal,
): Promise<void> {
  if (!response.body) throw new ContractError('empty event stream')
  const reader = response.body.getReader()
  const abort = () => { void reader.cancel().catch(() => {}) }
  signal?.addEventListener('abort', abort, { once: true })
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    signal?.throwIfAborted()
    for (;;) {
      const { value, done } = await reader.read()
      signal?.throwIfAborted()
      buffer += decoder.decode(value, { stream: !done })
      const blocks = buffer.split(/\r?\n\r?\n/)
      buffer = done ? '' : (blocks.pop() ?? '')
      for (const block of blocks) {
        signal?.throwIfAborted()
        const event = parseBlock(block, schema)
        if (event !== null) onEvent(event)
      }
      if (done) return
    }
  } finally {
    signal?.removeEventListener('abort', abort)
    try { await reader.cancel() } catch { /* Already errored or aborted. */ }
    reader.releaseLock()
  }
}
