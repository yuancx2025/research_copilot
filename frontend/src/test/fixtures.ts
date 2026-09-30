import type { AppConfig, ConversationDetail, Run } from '../api/types'
export const config: AppConfig = { notion_backend: 'disabled', default_destination: '', sources: ['web'], csrf: null }
export const makeRun = (overrides: Partial<Run> = {}): Run => ({
  id: 'r1', conversation_id: 'c1', request_id: 'request-1', status: 'running', query: 'question',
  retry_of_run_id: null, error: null, last_seq: 0, created_at: '2026-09-29T10:00:00Z', finished_at: null, result: null,
  ...overrides,
})
export const makeDetail = (overrides: Partial<ConversationDetail> = {}): ConversationDetail => ({
  id: 'c1', title: 'First', created_at: '2026-09-29T10:00:00Z', updated_at: '2026-09-29T10:00:00Z',
  messages: [], runs: [], drafts: [], ...overrides,
})
