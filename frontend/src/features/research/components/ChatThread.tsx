import styles from '../research.module.css'
import { useEffect, useRef } from 'react'
import type { ConversationMessage, ProgressEvent, Run } from '../../../api/types'
import { MessageBubble } from './MessageBubble'
import { ProgressTimeline } from './ProgressTimeline'

export function ChatThread({
  placeholder,
  messages,
  streaming,
  progress,
  retryable,
  onRetry,
  retryPending = false,
}: {
  placeholder: string
  messages: ConversationMessage[]
  streaming: boolean
  progress: ProgressEvent[]
  retryable: Run | null
  retryPending?: boolean
  onRetry: () => void
}) {
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => {
    end.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' })
  }, [messages.length, progress.length])

  return (
    <div className={styles["thread"]} role="log" aria-label="Conversation messages">
      {!messages.length && !streaming && <p className={styles["placeholder"]}>{placeholder}</p>}
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      {retryable && (
        <button type="button" onClick={onRetry} disabled={streaming || retryPending}>
          Retry
        </button>
      )}
      {streaming && <ProgressTimeline events={progress} />}
      <div ref={end} />
    </div>
  )
}
