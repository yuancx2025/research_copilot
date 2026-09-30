import type { ConversationDetail, Run, RunStatus } from '../../../api/types'
export const isActive = (status: RunStatus) => status === 'queued' || status === 'running'
export function conversationView(detail: ConversationDetail | undefined) {
  const runs = detail?.runs ?? []
  const latest = runs.at(-1) ?? null
  const activeRun = runs.find((run) => isActive(run.status)) ?? null
  const resultRun = [...runs].reverse().find((run) => run.result && run.status !== 'superseded') ?? null
  return {
    messages: detail?.messages ?? [], latest, activeRun, resultRun,
    result: resultRun?.result ?? null,
    draft: [...(detail?.drafts ?? [])].reverse().find((draft) => draft.run_id === resultRun?.id) ?? null,
    replyTo: latest?.status === 'awaiting_clarification' ? latest : null,
    retryable: latest && (latest.status === 'interrupted' || latest.status === 'failed') ? latest : null,
  }
}
export function replaceRun(detail: ConversationDetail | undefined, run: Run): ConversationDetail | undefined {
  if (!detail) return detail
  return { ...detail, runs: detail.runs.some((item) => item.id === run.id)
    ? detail.runs.map((item) => item.id === run.id ? run : item) : [...detail.runs, run] }
}
