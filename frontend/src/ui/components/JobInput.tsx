import React, { useRef, useState } from 'react'
import { api } from '../../lib/api'
import { useInterview } from '../InterviewContext'
import { JobPreview } from './JobPreview'

/** One-click starter roles: a representative JD the extractor can parse, so a
 *  first-time visitor isn't staring at an empty box. */
const ROLES: { title: string; jd: string }[] = [
  { title: 'Software Engineer', jd: 'Software Engineer to design, build, and ship backend and full-stack features. Responsibilities: write clean, tested code, review peers’ work, and debug production issues. Requirements: strong data structures and algorithms, proficiency in one modern language (Python, Go, or TypeScript), REST APIs, SQL, and Git.' },
  { title: 'Product Manager', jd: 'Product Manager to own a product area end to end. Responsibilities: define the roadmap, write specs, prioritize the backlog, and partner with engineering and design to ship. Requirements: strong product sense, data-informed decision-making, stakeholder communication, and experience running discovery and A/B tests.' },
  { title: 'Data Analyst', jd: 'Data Analyst to turn raw data into decisions. Responsibilities: build dashboards, run ad-hoc analyses, and present findings to stakeholders. Requirements: advanced SQL, a BI tool (Looker/Tableau/Power BI), statistics fundamentals, and the ability to communicate insights clearly to non-technical partners.' },
  { title: 'Marketing Specialist', jd: 'Marketing Specialist to plan and run multi-channel campaigns. Responsibilities: content, email, and paid social; track funnel metrics; and report on ROI. Requirements: copywriting, campaign analytics, SEO basics, and experience with a marketing automation platform.' },
  { title: 'UX/UI Designer', jd: 'UX/UI Designer to craft intuitive, accessible product experiences. Responsibilities: user research, wireframes, high-fidelity mockups, and design-system work. Requirements: Figma, interaction and visual design, usability testing, and close collaboration with engineers.' },
  { title: 'Customer Service Rep', jd: 'Customer Service Representative to be the first line of support. Responsibilities: resolve tickets across chat, email, and phone; de-escalate issues; and surface recurring problems to the product team. Requirements: clear written and verbal communication, empathy, and CRM/helpdesk experience.' },
]

/** Step 1: pick a starter role or paste a job description; it's read when you
 *  click away (or immediately when a role is picked). */
export const JobInput: React.FC = () => {
  const { job, setJob } = useInterview()
  const [jobText, setJobText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const lastParsed = useRef('')

  async function parse(raw?: string) {
    const text = (raw ?? jobText).trim()
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

  function pick(sample: string) {
    setJobText(sample)
    parse(sample)
  }

  return (
    <div className="step-section">
      <div className="step-header">
        <div className="step-number" aria-hidden="true">1</div>
        <h2 className="step-title">Job description</h2>
      </div>

      <div className="role-pills" role="group" aria-label="Start from a common role">
        {ROLES.map((r) => (
          <button
            key={r.title}
            type="button"
            className="role-pill"
            onClick={() => pick(r.jd)}
            disabled={loading}
          >
            {r.title}
          </button>
        ))}
      </div>

      <div className="input-group">
        <label className="input-label" htmlFor="job-text">Or paste the job description</label>
        <textarea
          id="job-text"
          className="textarea-field"
          placeholder="Paste the role's description here — it's read automatically when you click away."
          value={jobText}
          onChange={(e) => setJobText(e.target.value)}
          onBlur={() => parse()}
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
