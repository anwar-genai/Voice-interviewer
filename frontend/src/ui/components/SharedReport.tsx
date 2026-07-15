import React, { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../lib/api'
import type { SharedReport as Shared } from '../../lib/types'
import { FeedbackSection, Score } from './FeedbackReport'

/** Route "/s/:token": a public, read-only feedback report — no login needed.
 *  Shows only scores + coaching text; the transcript and résumé stay private. */
export const SharedReport: React.FC = () => {
  const { token = '' } = useParams()
  const [report, setReport] = useState<Shared | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.getSharedReport(token).then(setReport).catch((e) => setError(e.message))
  }, [token])

  return (
    <>
      <header className="app-header">
        <div className="nav-inner">
          <span className="app-title"><span className="brand-dot" aria-hidden="true" /> AI Interview Coach</span>
          <Link className="btn btn-primary nav-cta" to="/">Practice your own →</Link>
        </div>
      </header>
      <div className="app-container">
        <main className="main-content">
          <div className="screen">
            {error && <div className="status-badge status-error" role="alert">⚠️ {error}</div>}
            {!report && !error && (
              <div className="status-badge status-ready" role="status"><span className="loading-spinner" /> Loading…</div>
            )}
            {report && (
              <>
                <h2 className="step-title screen-title">{report.job_title || 'Interview'} — practice interview</h2>
                <p className="disclosure">
                  Shared coaching report from {new Date(report.created_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })}.
                  AI-generated practice feedback, not a hiring decision.
                </p>
                <div className="vu-row">
                  <Score label="Overall" value={report.feedback.overall_score} />
                  <Score label="Technical" value={report.feedback.technical_score} />
                  <Score label="Communication" value={report.feedback.communication_score} />
                </div>
                <FeedbackSection title="Strengths" items={report.feedback.strengths} tone="good" />
                <FeedbackSection title="Areas to improve" items={report.feedback.improvements} tone="warm" />
                <FeedbackSection title="Recommendations" items={report.feedback.recommendations} tone="accent" />
              </>
            )}
          </div>
        </main>
      </div>
    </>
  )
}
