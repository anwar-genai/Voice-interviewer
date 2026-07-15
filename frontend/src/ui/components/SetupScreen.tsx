import React, { useEffect } from 'react'
import { useInterview } from '../InterviewContext'
import type { Job } from '../../lib/types'
import { JobInput } from './JobInput'
import { ResumeUpload } from './ResumeUpload'
import { ReadinessPanel } from './ReadinessPanel'

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true'

/** Guest (no-signup) demo: already-parsed sample data, so starting costs zero
 *  LLM calls. Deliberately no personal name in the résumé — the interviewer
 *  would address the guest by it. */
const DEMO_JOB: Job = {
  job_title: 'Software Engineer',
  job_type: 'full-time',
  location: null,
  start_date: null,
  qualifications:
    'Data structures and algorithms, one modern language (Python, Go, or TypeScript), REST APIs, SQL, Git',
  responsibilities:
    'Design, build, and ship backend and full-stack features; review peers’ work; debug production issues',
  benefits: null,
}
const DEMO_RESUME =
  'Software engineer with four years of experience across Python and TypeScript. ' +
  'Built and maintained REST APIs with FastAPI and PostgreSQL, including a payments ' +
  'service handling idempotent retries. Shipped React frontends, wrote unit and ' +
  'integration tests, and debugged production incidents on call. Comfortable with ' +
  'Git, code review, CI pipelines, and agile teamwork.'

/** Route "/": assemble a job + resume, consent, and start. */
export const SetupScreen: React.FC<{ guest?: boolean }> = ({ guest = false }) => {
  const { job, prefill } = useInterview()

  // Guests get a one-click demo: sample role + résumé are preloaded.
  useEffect(() => {
    if (guest && !job) prefill(DEMO_JOB, DEMO_RESUME)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [guest])

  return (
    <>
      <div className="setup-head">
        <div>
          <h2 className="setup-title">Set up your interview</h2>
          <p className="setup-sub">Add the role and your résumé — the interviewer adapts to both.</p>
        </div>
        {guest && (
          <p className="demo-note" role="note">
            <span className="demo-dot" aria-hidden="true" />
            Demo mode: a sample role &amp; résumé are loaded — just start the interview.
            Sign up to use your own.
          </p>
        )}
        {DEMO_MODE && (
          <p className="demo-note" role="note">
            <span className="demo-dot" aria-hidden="true" />
            Live demo: the interviewer runs during scheduled sessions — if one isn&rsquo;t
            live, the interview won&rsquo;t connect.
          </p>
        )}
      </div>
      <div className="steps-container">
        <JobInput />
        <ResumeUpload />
      </div>
      <div className="setup-footer">
        <ReadinessPanel />
      </div>
    </>
  )
}
