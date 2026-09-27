import { useState, type FormEvent, type KeyboardEvent } from 'react'
import { clearConversation, sendMessage, useResearchStore } from '../../store/researchStore'

export function Composer({ placeholder }: { placeholder: string }) {
  const streaming = useResearchStore((state) => state.streaming)
  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)

  const submit = (event?: FormEvent) => {
    event?.preventDefault()
    if (!text.trim() || streaming) return
    setError(null)
    const message = text
    setText('')
    void sendMessage(message)
  }

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) submit(event)
  }

  const clear = async () => {
    setError(null)
    try {
      setError(await clearConversation())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not clear the conversation.')
    }
  }

  return (
    <form className="composer" onSubmit={submit}>
      <textarea
        aria-label="Message"
        placeholder={placeholder}
        value={text}
        rows={2}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={onKeyDown}
      />
      <div className="row">
        <button type="submit" className="primary" disabled={streaming || !text.trim()}>
          {streaming ? 'Researching…' : 'Submit'}
        </button>
        <button type="button" onClick={clear} disabled={streaming}>
          Clear
        </button>
      </div>
      {error && <p className="notice error">{error}</p>}
    </form>
  )
}
