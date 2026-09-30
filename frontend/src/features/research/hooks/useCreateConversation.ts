import { useMutation, useQueryClient } from '@tanstack/react-query'
import { createConversation } from '../../../api/endpoints/conversations'
import { researchKeys } from '../queries'
export function useCreateConversation() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: createConversation, retry: false,
    onSuccess: () => client.invalidateQueries({ queryKey: researchKeys.lists() }),
  })
}
