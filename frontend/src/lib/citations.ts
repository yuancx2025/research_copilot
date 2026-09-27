import type { Citation } from '../api/types'

export const SOURCE_LABELS: Record<string, string> = {
  arxiv: 'ArXiv Papers',
  youtube: 'YouTube Videos',
  github: 'GitHub Repositories',
  web: 'Web Articles',
  local: 'Local Documents',
  notion: 'Notion Pages',
  unknown: 'Other Sources',
}

export const SHORT_LABELS: Record<string, string> = {
  arxiv: 'ArXiv',
  youtube: 'YouTube',
  github: 'GitHub',
  web: 'Web',
  local: 'Local documents',
  notion: 'Notion',
}

const DISPLAY_ORDER = ['arxiv', 'youtube', 'github', 'web', 'local', 'notion']

export function sourceLabel(source: string, short = false): string {
  const labels = short ? SHORT_LABELS : SOURCE_LABELS
  return labels[source] ?? source.charAt(0).toUpperCase() + source.slice(1)
}

export function groupCitations(citations: Citation[]): Array<[string, Citation[]]> {
  const groups = new Map<string, Citation[]>()
  for (const citation of citations) {
    const key = citation.source_type || 'unknown'
    groups.set(key, [...(groups.get(key) ?? []), citation])
  }
  const rank = (key: string) => {
    const index = DISPLAY_ORDER.indexOf(key)
    return index === -1 ? DISPLAY_ORDER.length : index
  }
  return [...groups.entries()].sort(([a], [b]) => rank(a) - rank(b) || a.localeCompare(b))
}

export function citationDetail(citation: Citation): string {
  const parts: string[] = []
  if (citation.authors.length) {
    const shown = citation.authors.slice(0, 3).join(', ')
    parts.push(citation.authors.length > 3 ? `${shown} et al.` : shown)
  }
  if (citation.channel) parts.push(citation.channel)
  if (citation.repo && citation.repo !== citation.title) parts.push(citation.repo)
  if (citation.date) parts.push(citation.date.slice(0, 10))
  return parts.join(' · ')
}
