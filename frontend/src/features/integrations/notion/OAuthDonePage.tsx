import styles from './notion.module.css'
import { useEffect } from 'react'
import { Link } from 'react-router-dom'

export function OAuthDonePage() {
  useEffect(() => {
    // Browsers only allow this for tabs opened by script, which the Connect button does.
    const timer = window.setTimeout(() => window.close(), 1500)
    return () => window.clearTimeout(timer)
  }, [])

  return (
    <div className={styles["oauth-done"]}>
      <h1>Notion connected</h1>
      <p>You can close this tab and return to Research Copilot.</p>
      <Link to="/research">Back to the app</Link>
    </div>
  )
}
