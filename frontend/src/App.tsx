import { useEffect } from 'react'
import { Navigate, NavLink, Route, Routes } from 'react-router-dom'
import { useAppConfig } from './hooks/useAppConfig'
import { recoverResearch } from './store/researchStore'
import { DocumentsPage } from './features/documents/DocumentsPage'
import { ResearchPage } from './features/research/ResearchPage'
import { ChatPage } from './features/research/ChatPage'
import { OAuthDonePage } from './features/notion/OAuthDonePage'

export function App() {
  const config = useAppConfig()

  useEffect(() => {
    if (config.data) void recoverResearch()
  }, [config.data])

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
                <NavLink to="/research">Research</NavLink>
                <NavLink to="/chat">Chat</NavLink>
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
                  <Route path="/research" element={<ResearchPage config={config.data} />} />
                  <Route path="/chat" element={<ChatPage />} />
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
