import { describe, expect, it } from 'vitest'
import type { Citation } from '../api/types'
import { citationDetail, groupCitations } from './citations'
import { describeProgress } from './progress'

const citation = (overrides: Partial<Citation>): Citation => ({
  source_type: 'web',
  title: 'Title',
  url: 'https://example.com',
  snippet: '',
  authors: [],
  date: null,
  channel: null,
  repo: null,
  ...overrides,
})

describe('citations', () => {
  it('groups by source in the display order', () => {
    const groups = groupCitations([
      citation({ source_type: 'web' }),
      citation({ source_type: 'custom' }),
      citation({ source_type: 'arxiv' }),
      citation({ source_type: 'web', title: 'Second' }),
    ])
    expect(groups.map(([source, items]) => [source, items.length])).toEqual([
      ['arxiv', 1],
      ['web', 2],
      ['custom', 1],
    ])
  })

  it('summarizes authors, channel, repo and date', () => {
    expect(citationDetail(citation({ authors: ['A', 'B', 'C', 'D'], date: '2017-06-12T00:00:00' }))).toBe(
      'A, B, C et al. · 2017-06-12',
    )
    expect(citationDetail(citation({ channel: 'Channel' }))).toBe('Channel')
    expect(citationDetail(citation({ title: 'org/repo', repo: 'org/repo' }))).toBe('')
  })
})

describe('describeProgress', () => {
  it('tracks selected agents until each finishes', () => {
    const view = describeProgress([
      { type: 'progress', seq: 1, run_id: 'r1', node: 'prepare' },
      { type: 'progress', seq: 2, run_id: 'r1', node: 'classify_intent', agents: ['arxiv', 'web'] },
      { type: 'progress', seq: 3, run_id: 'r1', node: 'arxiv_agent', source: 'arxiv' },
    ])
    expect(view.done).toEqual(['Preparing sources', 'Selected ArXiv, Web', 'ArXiv search finished'])
    expect(view.current).toBe('Searching Web')
  })

  it('reports writing once every agent is done', () => {
    const view = describeProgress([
      { type: 'progress', seq: 4, run_id: 'r1', node: 'classify_intent', agents: ['web'] },
      { type: 'progress', seq: 5, run_id: 'r1', node: 'web_agent', source: 'web' },
    ])
    expect(view.current).toBe('Writing the answer')
    expect(describeProgress([]).current).toBe('Starting')
  })
})
