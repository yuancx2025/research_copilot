import { useQuery } from '@tanstack/react-query'
import { fetchConfig } from '../api/endpoints/config'

export function useAppConfig() {
  return useQuery({ queryKey: ['config'], queryFn: ({ signal }) => fetchConfig(signal), staleTime: Infinity })
}
