import { Navigate, Route, Routes, useOutletContext } from 'react-router-dom'
import type { AppConfig } from '../api/types'
import { DocumentsPage } from '../features/documents'
import { ResearchPage, ChatPage } from '../features/research'
import { OAuthDonePage } from '../features/integrations/notion'
import { AppLayout } from './AppLayout'
function ResearchRoute() { return <ResearchPage config={useOutletContext<AppConfig>()} /> }
export function AppRouter() {
  return <Routes>
    <Route path="/oauth/done" element={<OAuthDonePage />} />
    <Route element={<AppLayout />}>
      <Route index element={<Navigate to="/research" replace />} />
      <Route path="research/:conversationId?" element={<ResearchRoute />} />
      <Route path="chat/:conversationId?" element={<ChatPage />} />
      <Route path="documents" element={<DocumentsPage />} />
      <Route path="*" element={<Navigate to="/research" replace />} />
    </Route>
  </Routes>
}
