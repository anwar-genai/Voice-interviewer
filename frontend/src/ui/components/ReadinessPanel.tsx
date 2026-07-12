import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useInterview } from '../InterviewContext'

/** The consent + readiness checklist + "start" gate at the bottom of setup. */
export const ReadinessPanel: React.FC = () => {
  const { job, resume, consent, setConsent, room } = useInterview()
  const navigate = useNavigate()
  const [starting, setStarting] = useState(false)

  const allReady = !!job && !!resume && consent
  const canStart = allReady && !starting

  async function start() {
    if (!job || !resume || !consent) return
    setStarting(true)
    try {
      await room.start(job, resume, consent)
      navigate('/interview')
    } catch {
      // room.start already surfaced a friendly message in room.error.
    } finally {
      setStarting(false)
    }
  }

  const hint = !job && !resume
    ? 'Add a job description and upload your résumé to begin.'
    : !job
      ? 'Add a job description above to continue.'
      : !resume
        ? 'Upload your résumé above to continue.'
        : 'Check the consent box above to begin.'

  return (
    <div className="ready-panel">
      <div className="lamps">
        <span className={job ? 'lamp on' : 'lamp'}><span className="bulb" aria-hidden="true" /> Role loaded</span>
        <span className={resume ? 'lamp on' : 'lamp'}><span className="bulb" aria-hidden="true" /> Résumé loaded</span>
        <span className={consent ? 'lamp on' : 'lamp'}><span className="bulb" aria-hidden="true" /> Consent given</span>
      </div>

      <label className="consent-label">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <span>
          I consent to voice recording and résumé processing. The interviewer and feedback are{' '}
          <strong>AI-generated</strong> — coaching, not a hiring decision.
        </span>
      </label>

      {allReady && <div className="ready-badge"><span className="ready-dot" aria-hidden="true" /> You&rsquo;re all set</div>}
      <p className="standby">{allReady ? 'Find a quiet spot and check your mic. Start whenever you’re ready.' : hint}</p>

      <button className="btn btn-primary btn-full btn-lg btn-start" onClick={start} disabled={!canStart} aria-busy={starting}>
        {starting ? <span className="loading-spinner" /> : null} Start interview →
      </button>

      {room.error && <div className="status-badge status-error" role="alert">⚠️ {room.error}</div>}
    </div>
  )
}
