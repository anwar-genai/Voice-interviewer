import React, { useRef, useState } from 'react'
import { api } from '../../lib/api'
import { useInterview } from '../InterviewContext'
import { JobPreview } from './JobPreview'

/** Step 1: paste a job description; it's read automatically when you click away. */
export const JobInput: React.FC = () => {
  const { job, setJob } = useInterview()
  const [jobText, setJobText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const lastParsed = useRef('')

  async function parse() {
    const text = jobText.trim()
    if (!text || text === lastParsed.current || loading) return
    lastParsed.current = text
    setLoading(true)
    setError('')
    try {
      setJob(await api.parseJobText(text))
    } catch (err) {
      lastParsed.current = '' // let the same text be retried
      setError(err instanceof Error ? err.message : 'Could not read that job description.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="step-section">
      <div className="step-header">
        <div className="step-number" aria-hidden="true">1</div>
        <h2 className="step-title">Job description</h2>
      </div>

      <div className="input-group">
        <label className="input-label" htmlFor="job-text">Paste the job description</label>
        <textarea
          id="job-text"
          className="textarea-field"
          placeholder="Paste the role's description here — it's read automatically when you click away."
          value={jobText}
          onChange={(e) => setJobText(e.target.value)}
          onBlur={parse}
        />
        {loading && (
          <div className="status-badge status-ready" role="status"><span className="loading-spinner" /> Reading the job description…</div>
        )}
        {error && <div className="status-badge status-error" role="alert">⚠️ {error}</div>}
      </div>

      {job && <JobPreview job={job} />}
    </div>
  )
}
