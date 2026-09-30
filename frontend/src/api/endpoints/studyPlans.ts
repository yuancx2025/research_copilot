import { getJson, sendJson } from '../client'
import { zDraftOut, zExportOut } from '../contracts/generated/zod.gen'
import type { PreviewRequest, ExportRequest } from '../contracts/generated/types.gen'
export const previewStudyPlan = (runId: string) => sendJson('/api/study-plan/preview', 'POST', zDraftOut, { run_id: runId } satisfies PreviewRequest)
export const fetchDraft = (id: string, signal?: AbortSignal) => getJson(`/api/study-plan/drafts/${encodeURIComponent(id)}`, zDraftOut, signal)
export const exportStudyPlan = (draftId: string, destination: string) =>
  sendJson('/api/study-plan/export', 'POST', zExportOut, { draft_id: draftId, destination } satisfies ExportRequest)
