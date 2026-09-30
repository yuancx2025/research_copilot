import styles from './AppLayout.module.css'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAppConfig } from './useAppConfig'
function sectionPath(section: string, pathname: string) {
  const conversationId = pathname.match(/^\/(?:research|chat)\/([^/]+)/)?.[1]
  return conversationId ? `/${section}/${conversationId}` : `/${section}`
}
export function AppLayout() {
  const config = useAppConfig()
  const location = useLocation()
  return <div className={styles["shell"]}>
    <header className={styles["shell-header"]}>
      <h1>Research Copilot</h1>
      <nav className={styles["tabs"]} aria-label="Sections">
        <NavLink to={sectionPath('research', location.pathname)}>Research</NavLink>
        <NavLink to={sectionPath('chat', location.pathname)}>Chat</NavLink>
        <NavLink to="/documents">Documents</NavLink>
      </nav>
    </header>
    <main>{config.isError ? <div className="notice error" role="alert">
      <p>Could not load the application configuration. {config.error.message}</p>
      <button onClick={() => void config.refetch()}>Retry connection</button>
    </div> : !config.data ? <p className="muted">Loading…</p> : <Outlet context={config.data} />}</main>
  </div>
}
