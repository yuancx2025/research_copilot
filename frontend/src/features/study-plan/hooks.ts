import { skipToken, useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { ApiError } from '../../api/client'
import { exportStudyPlan, previewStudyPlan } from '../../api/endpoints/studyPlans'
import type { ExportResult, Run } from '../../api/types'
import { refreshConversation } from '../research/queries'
import { studyPlanKeys } from './queries'

export function usePreviewStudyPlan() {
  const client = useQueryClient()
  return useMutation({ retry: false, mutationFn: (run: Run) => previewStudyPlan(run.id),
    onSuccess: async (draft, run) => {
      client.setQueryData(studyPlanKeys.draft(draft.draft_id), draft)
      await refreshConversation(client, run.conversation_id)
    },
  })
}

const inflight = new WeakMap<QueryClient, Map<string, Promise<ExportResult>>>()
export function exportSavedDraft(client: QueryClient, draftId: string, destination: string): Promise<ExportResult> {
  let requests = inflight.get(client)
  if (!requests) { requests = new Map(); inflight.set(client, requests) }
  const pending = requests.get(draftId)
  if (pending) return pending
  const saved = client.getQueryData<ExportResult>(studyPlanKeys.export(draftId))
  if (saved && !saved.retryable) return Promise.resolve(saved)
  // Retain uncertain outcomes through feature unmounts for this application session.
  client.setQueryDefaults(studyPlanKeys.export(draftId), { gcTime: Infinity })
  const request = (async () => {
    let result: ExportResult
    try { result = await exportStudyPlan(draftId, destination) }
    catch (error) {
      const rejected = error instanceof ApiError && error.status >= 400 && error.status < 500
      result = { status: rejected ? 'failure' : 'unknown', page_id: null, url: null, retryable: rejected,
        message: rejected ? error.message : 'The export outcome could not be confirmed. Check Notion before trying again.' }
    }
    client.setQueryData(studyPlanKeys.export(draftId), result)
    return result
  })().finally(() => { requests.delete(draftId) })
  requests.set(draftId, request)
  return request
}
export function useExportStudyPlan(draftId: string) {
  const client = useQueryClient()
  const result = useQuery<ExportResult>({ queryKey: studyPlanKeys.export(draftId), queryFn: skipToken, gcTime: Infinity })
  const mutation = useMutation({ mutationKey: studyPlanKeys.export(draftId), retry: false,
    mutationFn: (destination: string) => exportSavedDraft(client, draftId, destination) })
  return { ...mutation, result: result.data }
}
