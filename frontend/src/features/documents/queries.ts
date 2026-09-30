import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query'
import { clearDocuments, listDocuments } from '../../api/endpoints/documents'
export const documentKeys = { all: ['documents'] as const }
export const documentOptions = () => queryOptions({
  queryKey: documentKeys.all, queryFn: ({ signal }) => listDocuments(signal),
})
export function useClearDocuments() {
  const client = useQueryClient()
  return useMutation({ mutationFn: clearDocuments, retry: false,
    onSuccess: (data) => client.setQueryData(documentKeys.all, data) })
}
