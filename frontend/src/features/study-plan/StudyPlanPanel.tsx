import styles from './studyPlan.module.css'
import { useRef, useState } from 'react'
import type { AppConfig, Draft, Run } from '../../api/types'
import { Markdown } from '../../shared/components/Markdown'
import { DestinationPicker } from '../integrations/notion'
import { useExportStudyPlan, usePreviewStudyPlan } from './hooks'

function ExportForm({ draft, config }: { draft: Draft; config: AppConfig }) {
  const [destination, setDestination] = useState(config.default_destination)
  const action = useExportStudyPlan(draft.draft_id)
  const result = action.result
  const locked = Boolean(result && !result.retryable)
  return <div className={styles["export-form"]}>
    {config.notion_backend === 'mcp' && <DestinationPicker onPick={setDestination} />}
    <label>Destination page URL or UUID
      <input value={destination} onChange={(event) => setDestination(event.target.value)} disabled={locked || !draft.exportable} />
    </label>
    <button className="primary" onClick={() => void action.mutateAsync(destination.trim())}
      disabled={action.isPending || locked || !destination.trim() || !draft.exportable}>
      {action.isPending ? 'Exporting…' : 'Export displayed plan'}
    </button>
    {!draft.exportable && <p className="notice error">This preview belongs to an earlier Notion connection. Generate a new one.</p>}
    {result && (result.status === 'success' && result.url
      ? <p className="notice ok">Created <a href={result.url} target="_blank" rel="noopener noreferrer">{draft.title}</a> in Notion.</p>
      : <p className={`notice ${result.status === 'success' ? 'ok' : 'error'}`} role="status">{result.message}</p>)}
  </div>
}
export function StudyPlanPanel({ config, run, draft, busy = false }: {
  config: AppConfig; run: Run | null; draft: Draft | null; busy?: boolean
}) {
  const action = usePreviewStudyPlan()
  const lock = useRef(false)
  const canPreview = Boolean(run?.result?.can_preview_plan)
  const preview = async () => {
    if (!run || lock.current) return
    lock.current = true
    try { await action.mutateAsync(run) } catch { /* Render mutation error. */ }
    finally { lock.current = false }
  }
  return <section className={["panel", styles["study-plan"]].join(' ')}>
    <h3>Notion study plan</h3>
    <button className="primary" onClick={preview} disabled={!canPreview || busy || action.isPending}>
      {action.isPending ? 'Generating preview…' : draft ? 'Regenerate preview' : 'Preview study plan'}
    </button>
    {!canPreview && !draft && <p className="muted">Run research that returns citations to preview a study plan.</p>}
    {action.error && <p className="notice error" role="alert">{action.error.message}</p>}
    {draft && <>
      <div className={styles["plan-preview"]}><Markdown>{draft.markdown}</Markdown></div>
      <ExportForm key={draft.draft_id} draft={draft} config={config} />
    </>}
  </section>
}
