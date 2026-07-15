import React from 'react'
import { JobInput } from './JobInput'
import { ResumeUpload } from './ResumeUpload'
import { ReadinessPanel } from './ReadinessPanel'

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true'

/** Route "/": assemble a job + resume, consent, and start. */
export const SetupScreen: React.FC = () => (
  <>
    <div className="setup-head">
      <div>
        <h2 className="setup-title">Set up your interview</h2>
        <p className="setup-sub">Add the role and your résumé — the interviewer adapts to both.</p>
      </div>
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
