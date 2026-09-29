import { useState, type FormEvent, type KeyboardEvent } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import type { Run } from '../../api/types'
import { sendMessage, useUiStore } from '../../store/researchStore'

export function Composer({ placeholder, replyTo }: { placeholder: string; replyTo: Run | null }) {
  const { conversationId } = useParams()
  const queryClient = useQueryClient()
  const streaming = useUiStore((state) => state.streamingRunId)
  const text = useUiStore((state) => (conversationId ? state.drafts[conversationId] ?? '' : ''))
  const setDraft = useUiStore((state) => state.setDraft)
  const [error, setError] = useState<string | null>(null)

  const submit = (event?: FormEvent) => {
    event?.preventDefault()
    if (!text.trim() || streaming || !conversationId) return
    setError(null)
    const message = text
    setDraft(conversationId, '')
    void sendMessage(queryClient, conversationId, message, replyTo ?? undefined).catch((err) => {
      setDraft(conversationId, message)
      setError(err instanceof Error ? err.message : 'Research could not start.')
    })
  }

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) submit(event)
  }

  return (
    <form className="composer" onSubmit={submit}>
      <textarea
        aria-label="Message"
        placeholder={conversationId ? placeholder : 'Start a new conversation to ask a question.'}
        value={text}
        rows={2}
        disabled={!conversationId}
        onChange={(event) => conversationId && setDraft(conversationId, event.target.value)}
        onKeyDown={onKeyDown}
      />
      <div className="row">
        <button type="submit" className="primary" disabled={!!streaming || !text.trim() || !conversationId}>
          {streaming ? 'Researching…' : replyTo ? 'Reply' : 'Submit'}
        </button>
      </div>
      {error && <p className="notice error">{error}</p>}
    </form>
  )
}
