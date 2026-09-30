import type { PropsWithChildren } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { ContractError } from '../api/validation'
import { ApiError } from '../api/client'
const queryClient = new QueryClient({ defaultOptions: {
  queries: { retry: (count, error) => count < 1 && !(error instanceof ContractError) && !(error instanceof ApiError && error.status < 500) },
  mutations: { retry: false },
} })
export function AppProviders({ children }: PropsWithChildren) {
  return <QueryClientProvider client={queryClient}><BrowserRouter>{children}</BrowserRouter></QueryClientProvider>
}
