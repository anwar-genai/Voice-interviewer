import React, { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../../lib/api'
import { useInterview } from '../InterviewContext'
import type { Feedback, InterviewDetail, Job } from '../../lib/types'
import { JobPreview } from './JobPreview'
import { VuMeter } from './instruments'

const TONE = { good: 'var(--good)', warm: 'var(--warm)', accent: 'var(--accent)' } as const

export const FeedbackSection: React.FC<{ title: string; items: string[]; tone: keyof typeof TONE }> = ({ title, items, tone }) => {
  if (!items?.length) return null
  return (
    <div className="fb-section">
      <h3><span className="tag" style={{ background: TONE[tone] }} aria-hidden="true" /> {title}</h3>
      <ul className="feedback-list">
        {items.map((item, i) => <li key={i}>{item}</li>)}
      </ul>
    </div>
  )
}

export const Score: React.FC<{ label: string; value: number }> = ({ label, value }) => (
  <div className="vu-cell" aria-label={`${label} score ${value} out of 10`}>
    <VuMeter value={value} />
    <div className="k">{label}</div>
    <div className="v">{value}<small>/10</small></div>
  </div>
)

/** Route "/feedback/:id": show the scored feedback, generating it if needed. */
export const FeedbackReport: React.FC = () => {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const { prefill, reset } = useInterview()
  const [feedback, setFeedback] = useState<Feedback | null>(null)
  const [detail, setDetail] = useState<InterviewDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [shareToken, setShareToken] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const shareUrl = shareToken ? `${window.location.origin}/s/${shareToken}` : ''

  function copy(text: string) {
    navigator.clipboard?.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }).catch(() => {}) // no clipboard (http/older browser): the visible URL is the fallback
  }

  async function share() {
    try {
      const { token } = await api.shareInterview(id)
      setShareToken(token)
      copy(`${window.location.origin}/s/${token}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create the share link')
    }
  }

  async function unshare() {
    try {
      await api.unshareInterview(id)
      setShareToken(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stop sharing')
    }
  }

  async function loadFeedback(forceGenerate = false) {
    setError('')
    setFeedback(null)
    setLoading(true)
    try {
      // Read the stored score; if it isn't there yet (just-ended interview),
      // generate it. Scoring is idempotent server-side, so this never double-bills.
      const fb = forceGenerate
        ? await api.generateFeedback(id)
        : await api.getFeedback(id).catch(() => api.generateFeedback(id))
      setFeedback(fb)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load feedback')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setDetail(null)
    api.getInterview(id).then((d) => {
      setDetail(d)
      setShareToken(d.share_token)
    }).catch(() => {}) // transcript/JD are nice-to-have
    loadFeedback()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  function retake() {
    if (!detail) return
    prefill(Object.keys(detail.job || {}).length ? (detail.job as Job) : null, detail.resume || '')
    navigate('/')
  }
  function newInterview() {
    reset()
    navigate('/')
  }

  return (
    <div className="screen">
      <h2 className="step-title screen-title">Interview feedback</h2>
      <p className="disclosure">This feedback is AI-generated coaching, not a hiring decision.</p>

      {loading && <div className="status-badge status-ready" role="status"><span className="loading-spinner" /> Scoring your interview…</div>}
      {error && <div className="status-badge status-error" role="alert">⚠️ {error}</div>}
      {error && !loading && (
        <div className="retry-row">
          <button className="btn btn-primary" onClick={() => loadFeedback(true)}>Try scoring again</button>
        </div>
      )}

      {feedback && (
        <>
          <div className="vu-row">
            <Score label="Overall" value={feedback.overall_score} />
            <Score label="Technical" value={feedback.technical_score} />
            <Score label="Communication" value={feedback.communication_score} />
          </div>
          <FeedbackSection title="Strengths" items={feedback.strengths} tone="good" />
          <FeedbackSection title="Areas to improve" items={feedback.improvements} tone="warm" />
          <FeedbackSection title="Recommendations" items={feedback.recommendations} tone="accent" />

          <div className="share-row">
            {shareToken ? (
              <>
                <button className="btn btn-secondary" onClick={() => copy(shareUrl)}>
                  {copied ? '✓ Copied' : 'Copy share link'}
                </button>
                <button className="btn btn-secondary" onClick={unshare}>Stop sharing</button>
                <code className="share-url">{shareUrl}</code>
                <p className="share-hint">
                  Anyone with the link sees the scores and feedback — never your transcript or résumé.
                </p>
              </>
            ) : (
              <button className="btn btn-secondary" onClick={share}>Share this report</button>
            )}
          </div>
        </>
      )}

      {detail && detail.turns.length > 0 && (
        <div className="preview-section">
          <h3 className="preview-title">Transcript</h3>
          <div className="preview-content transcript">
            {detail.turns.map((t, i) => (
              <p key={i}><span className="who">{t.role === 'agent' ? 'Interviewer' : 'You'}</span> {t.content}</p>
            ))}
          </div>
        </div>
      )}

      {detail && <JobPreview job={detail.job} title="Job description" />}

      <div className="interview-controls screen-actions">
        <Link className="btn btn-secondary" to="/history">History</Link>
        {detail && <button className="btn btn-secondary" onClick={retake}>Retake</button>}
        <button className="btn btn-primary" onClick={newInterview}>New interview</button>
      </div>
    </div>
  )
}
