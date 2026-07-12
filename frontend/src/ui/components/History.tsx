import React, { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../../lib/api'
import { useInterview } from '../InterviewContext'
import type { InterviewSummary, Job } from '../../lib/types'
import { MiniWave, ScoreRing } from './instruments'

/** Stable per-interview seed so each card's waveform is its own but consistent. */
function seedFrom(id: string): number {
  let h = 0
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) | 0
  return Math.abs(h) || 1
}

const shortDate = (iso: string) =>
  new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })

/** Route "/history": the caller's past interviews as recording cards. */
export const History: React.FC = () => {
  const navigate = useNavigate()
  const { prefill } = useInterview()
  const [interviews, setInterviews] = useState<InterviewSummary[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.listInterviews().then(setInterviews).catch((e) => setError(e.message))
  }, [])

  async function retake(id: string) {
    setError('')
    try {
      const iv = await api.getInterview(id)
      prefill(Object.keys(iv.job || {}).length ? (iv.job as Job) : null, iv.resume || '')
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load that interview')
    }
  }

  return (
    <div className="screen">
      <h2 className="step-title screen-title">Your interviews</h2>
      {error && <div className="status-badge status-error" role="alert">⚠️ {error}</div>}

      {interviews === null && !error && (
        <div className="status-badge status-ready" role="status"><span className="loading-spinner" /> Loading…</div>
      )}
      {interviews?.length === 0 && <p className="ready-hint">No interviews yet. Start one to see it here.</p>}

      {interviews && interviews.length > 0 && (
        <div className="episodes">
          {interviews.map((iv) => {
            const scored = iv.overall_score != null
            const statusLabel = scored ? 'Scored' : iv.status === 'created' ? 'Not started' : 'Not scored'
            const chipClass = scored ? (iv.overall_score! >= 7 ? 'chip-good' : 'chip-amber') : 'chip-muted'
            return (
              <div key={iv.id} className="episode">
                <div className="episode-top">
                  <span className="take">{shortDate(iv.created_at)}</span>
                  <span className={`chip ${chipClass}`}>{statusLabel}</span>
                </div>
                <div className="title">{iv.job_title || 'Interview'}</div>
                <div className="episode-mid">
                  <MiniWave seed={seedFrom(iv.id)} />
                  <ScoreRing value={iv.overall_score} />
                </div>
                <div className="episode-actions">
                  {scored && <Link className="btn btn-secondary" to={`/feedback/${iv.id}`}>View feedback</Link>}
                  {!scored && iv.status !== 'created' && (
                    <button className="btn btn-secondary" onClick={() => navigate(`/feedback/${iv.id}`)}>Score</button>
                  )}
                  <button className="btn btn-secondary" onClick={() => retake(iv.id)}>Retake</button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      <div className="interview-controls screen-actions">
        <Link className="btn btn-primary" to="/">New interview</Link>
      </div>
    </div>
  )
}
