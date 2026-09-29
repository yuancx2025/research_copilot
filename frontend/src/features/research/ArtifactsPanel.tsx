import type { Citation, ResearchResult } from '../../api/types'
import { citationDetail, groupCitations, sourceLabel } from '../../lib/citations'

function SourcesSummary({ sources }: { sources: Record<string, number> }) {
  const entries = Object.entries(sources)
  if (!entries.length) return <p className="muted">No sources used yet.</p>
  return (
    <ul className="sources">
      {entries.map(([source, count]) => (
        <li key={source}>
          <strong>{sourceLabel(source, true)}</strong>: {count} result{count === 1 ? '' : 's'}
        </li>
      ))}
    </ul>
  )
}

function CitationItem({ citation }: { citation: Citation }) {
  const detail = citationDetail(citation)
  return (
    <li>
      {citation.url ? (
        <a href={citation.url} target="_blank" rel="noopener noreferrer">
          {citation.title}
        </a>
      ) : (
        <span>{citation.title}</span>
      )}
      {detail && <span className="citation-detail">{detail}</span>}
    </li>
  )
}

export function ArtifactsPanel({ result }: { result: ResearchResult | null }) {
  const groups = groupCitations(result?.citations ?? [])
  return (
    <section className="panel">
      <h3>Research sources</h3>
      <SourcesSummary sources={result?.sources ?? {}} />
      <h3>Citations</h3>
      <div className="citations">
        {groups.length ? (
          groups.map(([source, citations]) => (
            <div key={source} className="citation-group">
              <h4>{sourceLabel(source)}</h4>
              <ul>
                {citations.map((citation, index) => (
                  <CitationItem key={`${citation.url}-${index}`} citation={citation} />
                ))}
              </ul>
            </div>
          ))
        ) : (
          <p className="muted">No citations yet.</p>
        )}
      </div>
    </section>
  )
}
