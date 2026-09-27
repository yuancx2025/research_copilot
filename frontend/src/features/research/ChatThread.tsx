import { useEffect, useRef } from 'react'
import { useResearchStore } from '../../store/researchStore'
import { MessageBubble } from './MessageBubble'
import { ProgressTimeline } from './ProgressTimeline'

export function ChatThread({ placeholder }: { placeholder: string }) {
  const messages = useResearchStore((state) => state.messages)
  const streaming = useResearchStore((state) => state.streaming)
  const progress = useResearchStore((state) => state.progress)
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => {
    end.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' })
  }, [messages.length, progress.length])

  return (
    <div className="thread">
      {!messages.length && !streaming && <p className="placeholder">{placeholder}</p>}
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      {streaming && <ProgressTimeline events={progress} />}
      <div ref={end} />
    </div>
  )
}
