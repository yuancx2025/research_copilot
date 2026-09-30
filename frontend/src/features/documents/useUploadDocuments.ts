import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { uploadDocuments } from '../../api/endpoints/documents'
import type { UploadEvent } from '../../api/types'
import { ContractError } from '../../api/validation'
import { documentKeys } from './queries'

type Progress = Extract<UploadEvent, { type: 'progress' }>
export function useUploadDocuments() {
  const client = useQueryClient()
  const [progress, setProgress] = useState<Progress | null>(null)
  const mutation = useMutation({
    retry: false,
    mutationFn: async (files: File[]) => {
      setProgress({ type: 'progress', fraction: 0, message: 'Uploading' })
      const outcome: { result?: Extract<UploadEvent, { type: 'result' }> } = {}
      try {
        await uploadDocuments(files, (event) => {
          if (event.type === 'progress') setProgress(event)
          else if (event.type === 'error') throw new Error(event.message)
          else { outcome.result = event; client.setQueryData(documentKeys.all, { documents: event.documents }) }
        })
        if (!outcome.result) throw new ContractError('upload ended without result')
        return outcome.result
      } finally {
        setProgress(null)
        void client.invalidateQueries({ queryKey: documentKeys.all })
      }
    },
  })
  return { ...mutation, progress }
}
