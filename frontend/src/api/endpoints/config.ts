import { getJson, setCsrfToken } from '../client'
import { zConfigOut } from '../contracts/generated/zod.gen'
export async function fetchConfig(signal?: AbortSignal) {
  const config = await getJson('/api/config', zConfigOut, signal)
  setCsrfToken(config.csrf)
  return config
}
