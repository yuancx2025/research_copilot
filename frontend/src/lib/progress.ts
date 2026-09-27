import type { ProgressEvent } from '../api/types'
import { sourceLabel } from './citations'

export interface ProgressView {
  done: string[]
  searching: string[]
  current: string | null
}

const NODE_LABELS: Record<string, string> = {
  prepare: 'Preparing sources',
  summarize: 'Reviewed the conversation',
  analyze_rewrite: 'Understood the question',
  aggregate: 'Wrote the answer',
}

function label(event: ProgressEvent): string | null {
  if (event.node === 'classify_intent') {
    const agents = event.agents ?? []
    return agents.length ? `Selected ${agents.map((a) => sourceLabel(a, true)).join(', ')}` : 'Selected sources'
  }
  if (event.source) return `${sourceLabel(event.source, true)} search finished`
  if (event.node === 'analyze_rewrite' && event.clear === false) return 'Needs clarification'
  return NODE_LABELS[event.node] ?? null
}

export function describeProgress(events: ProgressEvent[]): ProgressView {
  const done = events.map(label).filter((text): text is string => Boolean(text))
  const selected = events.find((e) => e.node === 'classify_intent')?.agents ?? []
  const finished = new Set(events.map((e) => e.source).filter(Boolean))
  const searching = selected.filter((agent) => !finished.has(agent))
  return { done, searching, current: currentStep(events[events.length - 1]?.node, searching) }
}

function currentStep(lastNode: string | undefined, searching: string[]): string | null {
  switch (lastNode) {
    case undefined:
      return 'Starting'
    case 'prepare':
      return 'Reviewing the conversation'
    case 'summarize':
      return 'Understanding the question'
    case 'analyze_rewrite':
      return 'Choosing sources'
    case 'aggregate':
      return null
    default:
      return searching.length
        ? `Searching ${searching.map((a) => sourceLabel(a, true)).join(', ')}`
        : 'Writing the answer'
  }
}
