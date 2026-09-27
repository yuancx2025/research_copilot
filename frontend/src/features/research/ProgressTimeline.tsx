import type { ProgressEvent } from '../../api/types'
import { describeProgress } from '../../lib/progress'

export function ProgressTimeline({ events }: { events: ProgressEvent[] }) {
  const { done, current } = describeProgress(events)
  return (
    <div className="progress-timeline" aria-live="polite">
      <ul>
        {done.map((step, index) => (
          <li key={`${index}-${step}`} className="step-done">
            {step}
          </li>
        ))}
        {current && <li className="step-current">{current}…</li>}
      </ul>
    </div>
  )
}
