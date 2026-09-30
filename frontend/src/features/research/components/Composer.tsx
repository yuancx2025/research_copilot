import styles from '../research.module.css'
import { useState, type FormEvent, type KeyboardEvent } from 'react'
import type { Run } from '../../../api/types'
import { useUiStore } from '../state/uiStore'
import { useResearchActions } from '../hooks/useResearchActions'

export function Composer({ placeholder, replyTo, conversationId, runActive }: {
  placeholder: string; replyTo: Run | null; conversationId?: string; runActive: boolean
}) {
  const text = useUiStore((state) => conversationId ? state.drafts[conversationId] ?? '' : '')
  const setDraft = useUiStore((state) => state.setDraft)
  const action = useResearchActions(conversationId ?? '')
  const [error, setError] = useState<string | null>(null)
  const submit = (event?: FormEvent) => {
    event?.preventDefault()
    if (!text.trim() || runActive || action.pending || !conversationId) return
    setError(null)
    void action.mutateAsync({ text, replyTo: replyTo?.id }).catch((err) => {
      setError(err instanceof Error ? err.message : 'Research could not start.')
    })
  }
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) submit(event)
  }
  return (
    <form className={styles["composer"]} onSubmit={submit}>
      <textarea aria-label="Message" placeholder={conversationId ? placeholder : 'Start a new conversation to ask a question.'}
        value={text} rows={2} disabled={!conversationId}
        onChange={(event) => conversationId && setDraft(conversationId, event.target.value)} onKeyDown={onKeyDown} />
      <div className="row">
        <button type="submit" className="primary" disabled={runActive || action.pending || !text.trim() || !conversationId}>
          {action.pending ? 'Submitting…' : runActive ? 'Researching…' : replyTo ? 'Reply' : 'Submit'}
        </button>
      </div>
      {error && <p className="notice error" role="alert">{error}</p>}
    </form>
  )
}
