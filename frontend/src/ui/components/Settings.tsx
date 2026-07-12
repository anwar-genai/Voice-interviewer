import React, { useState } from 'react'
import { api } from '../../lib/api'
import { useInterview } from '../InterviewContext'

/** Route "/settings": transparency + self-serve GDPR-style data deletion. */
export const Settings: React.FC = () => {
  const { reset } = useInterview()
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState<number | null>(null)

  async function deleteAll() {
    setBusy(true)
    setError('')
    try {
      const { deleted } = await api.deleteAllInterviews()
      setDone(deleted)
      setConfirming(false)
      reset() // drop any in-memory job/resume too
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete your data')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="screen">
      <h2 className="step-title screen-title">Privacy &amp; data</h2>

      <div className="preview-section">
        <h3 className="preview-title">How this works</h3>
        <p>
          The interviewer and the feedback are <strong>AI-generated</strong> — coaching practice, not a
          hiring decision. You give consent to voice recording and résumé processing each time you start
          an interview.
        </p>
      </div>

      <div className="preview-section">
        <h3 className="preview-title">What we keep</h3>
        <p>
          Per interview: the parsed job details, your résumé text, the conversation transcript, and the
          generated feedback — all tied to your account and visible only to you.
        </p>
      </div>

      <div className="preview-section danger-zone">
        <svg className="reel" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m2 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M10 11v6M14 11v6" />
        </svg>
        <div>
          <h3 className="preview-title">Delete everything</h3>
          <p>Permanently erase <strong>all</strong> of your interviews, transcripts and feedback. This cannot be undone.</p>

          {done != null ? (
            <div className="status-badge status-connected" role="status">✅ Deleted {done} interview{done === 1 ? '' : 's'}.</div>
          ) : !confirming ? (
            <button className="btn btn-danger" onClick={() => setConfirming(true)}>Delete all my data</button>
          ) : (
            <div className="confirm-row">
              <span style={{ fontWeight: 600 }}>Are you sure? This is permanent.</span>
              <button className="btn btn-danger" onClick={deleteAll} disabled={busy} aria-busy={busy}>
                {busy ? <span className="loading-spinner" /> : 'Yes, delete everything'}
              </button>
              <button className="btn btn-secondary" onClick={() => setConfirming(false)} disabled={busy}>Cancel</button>
            </div>
          )}
          {error && <div className="status-badge status-error" role="alert">⚠️ {error}</div>}
        </div>
      </div>
    </div>
  )
}
