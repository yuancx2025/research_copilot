import { useState } from 'react'
import { exportStudyPlan, previewStudyPlan } from '../../api/endpoints'
import type { AppConfig, Draft, ExportResult } from '../../api/types'
import { Markdown } from '../../components/Markdown'
import { useResearchStore } from '../../store/researchStore'
import { DestinationPicker } from './DestinationPicker'

function ExportForm({ draft, config }: { draft: Draft; config: AppConfig }) {
  const [destination, setDestination] = useState(config.default_destination)
  const [exporting, setExporting] = useState(false)
  const [result, setResult] = useState<ExportResult | null>(null)

  const publish = async () => {
    setExporting(true)
    try {
      setResult(await exportStudyPlan(draft.draft_id, destination.trim()))
    } catch (error) {
      setResult({
        status: 'failure',
        page_id: null,
        url: null,
        message: error instanceof Error ? error.message : 'Export could not complete.',
        retryable: true,
      })
    } finally {
      setExporting(false)
    }
  }

  const locked = result !== null && !result.retryable
  return (
    <div className="export-form">
      {config.notion_backend === 'mcp' && <DestinationPicker onPick={setDestination} />}
      <label>
        Destination page URL or UUID
        <input value={destination} onChange={(event) => setDestination(event.target.value)} disabled={locked} />
      </label>
      <button className="primary" onClick={publish} disabled={exporting || locked || !destination.trim()}>
        {exporting ? 'Exporting…' : 'Export displayed plan'}
      </button>
      {result &&
        (result.status === 'success' && result.url ? (
          <p className="notice ok">
            Created{' '}
            <a href={result.url} target="_blank" rel="noopener noreferrer">
              {draft.title}
            </a>{' '}
            in Notion.
          </p>
        ) : (
          <p className={`notice ${result.status === 'success' ? 'ok' : 'error'}`}>{result.message}</p>
        ))}
    </div>
  )
}

export function StudyPlanPanel({ config }: { config: AppConfig }) {
  const result = useResearchStore((state) => state.result)
  const draft = useResearchStore((state) => state.draft)
  const setDraft = useResearchStore((state) => state.setDraft)
  const streaming = useResearchStore((state) => state.streaming)
  const [previewing, setPreviewing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const preview = async () => {
    setPreviewing(true)
    setError(null)
    try {
      setDraft(await previewStudyPlan())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not generate a draft.')
    } finally {
      setPreviewing(false)
    }
  }

  return (
    <section className="panel study-plan">
      <h3>Notion study plan</h3>
      <button className="primary" onClick={preview} disabled={!result?.can_preview_plan || streaming || previewing}>
        {previewing ? 'Generating preview…' : draft ? 'Regenerate preview' : 'Preview study plan'}
      </button>
      {!result?.can_preview_plan && !draft && (
        <p className="muted">Run research that returns citations to preview a study plan.</p>
      )}
      {error && <p className="notice error">{error}</p>}
      {draft && (
        <>
          <div className="plan-preview">
            <Markdown>{draft.markdown}</Markdown>
          </div>
          <ExportForm key={draft.draft_id} draft={draft} config={config} />
        </>
      )}
    </section>
  )
}
