import type { ZodType } from 'zod'

export class ContractError extends Error {
  constructor(readonly context: string) {
    super('The server returned data this app could not understand. Refresh or reconnect to try again.')
    this.name = 'ContractError'
  }
}

export function validate<T>(schema: ZodType<T>, data: unknown, context: string): T {
  const result = schema.safeParse(data)
  if (!result.success) throw new ContractError(context)
  return result.data
}

export async function readJson<T>(response: Response, schema: ZodType<T>, context: string): Promise<T> {
  let data: unknown
  try {
    data = await response.json()
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') throw error
    throw new ContractError(context)
  }
  return validate(schema, data, context)
}
