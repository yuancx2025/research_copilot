import { getJson, sendJson, setCsrfToken } from '../client'
import { zPageOut, zNotionStatusOut, zNotionStartOut, zNotionDisconnectOut } from '../contracts/generated/zod.gen'
export const searchNotionPages = (query: string, signal?: AbortSignal) =>
  getJson(`/api/notion/pages?q=${encodeURIComponent(query)}`, zPageOut.array(), signal)
export async function fetchNotionStatus(signal?: AbortSignal) {
  const status = await getJson('/oauth/notion/status', zNotionStatusOut, signal)
  setCsrfToken(status.csrf)
  return status
}
export const startNotionAuthorization = () => sendJson('/oauth/notion/start', 'POST', zNotionStartOut)
export const disconnectNotion = () => sendJson('/oauth/notion/disconnect', 'POST', zNotionDisconnectOut)
