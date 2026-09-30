import { queryOptions } from '@tanstack/react-query'
import { fetchNotionStatus, searchNotionPages } from '../../../api/endpoints/notion'
export const notionKeys = {
  all: ['notion'] as const,
  status: () => ['notion', 'status'] as const,
  pages: () => ['notion', 'pages'] as const,
  search: (generation: string | null, query: string) => ['notion', 'pages', generation, query] as const,
}
export const notionStatusOptions = (enabled: boolean) => queryOptions({
  queryKey: notionKeys.status(), queryFn: ({ signal }) => fetchNotionStatus(signal), enabled,
  refetchInterval: (query) => query.state.data?.status === 'connecting' ? 2000 : 10000,
  refetchOnWindowFocus: true,
})
export const destinationOptions = (generation: string | null, query: string | null) => queryOptions({
  queryKey: notionKeys.search(generation, query ?? ''),
  queryFn: ({ signal }) => searchNotionPages(query ?? '', signal), enabled: query !== null,
})
