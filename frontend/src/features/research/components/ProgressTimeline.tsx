import styles from '../research.module.css'
import type { ProgressEvent } from '../../../api/types'
import { describeProgress } from '../model/progress'

export function ProgressTimeline({ events }: { events: ProgressEvent[] }) {
  const { done, current } = describeProgress(events)
  return (
    <div className={styles["progress-timeline"]} aria-live="polite">
      <ul>
        {done.map((step, index) => (
          <li key={`${index}-${step}`} className={styles["step-done"]}>
            {step}
          </li>
        ))}
        {current && <li className={styles["step-current"]}>{current}…</li>}
      </ul>
    </div>
  )
}
