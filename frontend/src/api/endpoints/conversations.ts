import { getJson, sendJson } from '../client'
import { zConversationOut, zConversationDetailOut } from '../contracts/generated/zod.gen'
export const listConversations = (signal?: AbortSignal) => getJson('/api/conversations', zConversationOut.array(), signal)
export const createConversation = () => sendJson('/api/conversations', 'POST', zConversationOut, {})
export const fetchConversation = (id: string, signal?: AbortSignal) =>
  getJson(`/api/conversations/${encodeURIComponent(id)}`, zConversationDetailOut, signal)
