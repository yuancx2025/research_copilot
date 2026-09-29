import { Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { useAppConfig } from './hooks/useAppConfig'
import { DocumentsPage } from './features/documents/DocumentsPage'
import { ResearchPage } from './features/research/ResearchPage'
import { ChatPage } from './features/research/ChatPage'
import { OAuthDonePage } from './features/notion/OAuthDonePage'

function sectionPath(section: string, pathname: string) {
  const conversationId = pathname.match(/^\/(?:research|chat)\/([^/]+)/)?.[1]
  return conversationId ? `/${section}/${conversationId}` : `/${section}`
}

export function App() {
  const config = useAppConfig()
  const location = useLocation()

  return (
    <Routes>
      <Route path="/oauth/done" element={<OAuthDonePage />} />
      <Route
        path="*"
        element={
          <div className="shell">
            <header className="shell-header">
              <h1>Research Copilot</h1>
              <nav className="tabs" aria-label="Sections">
                <NavLink to={sectionPath('research', location.pathname)}>Research</NavLink>
                <NavLink to={sectionPath('chat', location.pathname)}>Chat</NavLink>
                <NavLink to="/documents">Documents</NavLink>
              </nav>
            </header>
            <main>
              {config.isError ? (
                <p className="notice error">Could not reach the server. Check that the backend is running, then reload.</p>
              ) : !config.data ? (
                <p className="muted">Loading…</p>
              ) : (
                <Routes>
                  <Route path="/" element={<Navigate to="/research" replace />} />
                  <Route path="/research/:conversationId?" element={<ResearchPage config={config.data} />} />
                  <Route path="/chat/:conversationId?" element={<ChatPage />} />
                  <Route path="/documents" element={<DocumentsPage />} />
                  <Route path="*" element={<Navigate to="/research" replace />} />
                </Routes>
              )}
            </main>
          </div>
        }
      />
    </Routes>
  )
}
