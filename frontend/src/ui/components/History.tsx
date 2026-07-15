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

/** Overall score per scored interview, oldest → newest (last 10). Hidden until there are two. */
const ScoreTrend: React.FC<{ interviews: InterviewSummary[] }> = ({ interviews }) => {
  const scored = interviews
    .filter((iv) => iv.overall_score != null)
    .sort((a, b) => a.created_at.localeCompare(b.created_at))
    .slice(-10)
  if (scored.length < 2) return null

  const W = 560, H = 130, padL = 26, padR = 34, padT = 14, padB = 22
  const x = (i: number) => padL + (i * (W - padL - padR)) / (scored.length - 1)
  const y = (v: number) => padT + (1 - v / 10) * (H - padT - padB)
  const pts = scored.map((iv, i) => ({ cx: x(i), cy: y(iv.overall_score!), iv }))
  const line = pts.map((p, i) => `${i ? 'L' : 'M'}${p.cx.toFixed(1)} ${p.cy.toFixed(1)}`).join(' ')

  return (
    <div className="trend">
      <div className="trend-head">
        <span className="take">Progress</span>
        <span className="trend-sub">overall score · last {scored.length} scored</span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Overall scores, oldest to newest: ${scored.map((iv) => iv.overall_score).join(', ')} out of 10`}
      >
        {[0, 5, 10].map((v) => (
          <g key={v}>
            <line className="trend-grid" x1={padL} x2={W - padR} y1={y(v)} y2={y(v)} />
            <text className="trend-tick" x={padL - 7} y={y(v) + 3.5} textAnchor="end">{v}</text>
          </g>
        ))}
        <path className="trend-line" d={line} />
        {pts.map((p, i) => (
          <g key={p.iv.id}>
            <title>{`${shortDate(p.iv.created_at)} — ${p.iv.overall_score}/10${p.iv.job_title ? ` · ${p.iv.job_title}` : ''}`}</title>
            <circle cx={p.cx} cy={p.cy} r={11} fill="transparent" />
            <circle className="trend-dot" cx={p.cx} cy={p.cy} r={4} />
            {i === pts.length - 1 && (
              <text className="trend-last" x={p.cx + 10} y={p.cy + 3.5}>{p.iv.overall_score}</text>
            )}
          </g>
        ))}
        <text className="trend-tick" x={padL} y={H - 4}>{shortDate(scored[0].created_at)}</text>
        <text className="trend-tick" x={W - padR} y={H - 4} textAnchor="end">
          {shortDate(scored[scored.length - 1].created_at)}
        </text>
      </svg>
    </div>
  )
}

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

      {interviews && <ScoreTrend interviews={interviews} />}

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
