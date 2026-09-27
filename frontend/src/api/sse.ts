// EventSource only supports GET, so streamed POST responses are parsed here.

function parseBlock<T>(block: string): T | null {
  const data = block
    .split(/\r?\n/)
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart())
  return data.length ? (JSON.parse(data.join('\n')) as T) : null
}

export async function readEventStream<T>(response: Response, onEvent: (event: T) => void): Promise<void> {
  if (!response.body) throw new Error('The server returned an empty stream.')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    const blocks = buffer.split(/\r?\n\r?\n/)
    buffer = done ? '' : (blocks.pop() ?? '')
    for (const block of blocks) {
      const event = parseBlock<T>(block)
      if (event) onEvent(event)
    }
    if (done) return
  }
}
