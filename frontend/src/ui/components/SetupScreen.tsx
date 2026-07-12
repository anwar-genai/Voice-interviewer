import React from 'react'
import { JobInput } from './JobInput'
import { ResumeUpload } from './ResumeUpload'
import { ReadinessPanel } from './ReadinessPanel'

/** Route "/": assemble a job + resume, consent, and start. */
export const SetupScreen: React.FC = () => (
  <>
    <div className="steps-container">
      <JobInput />
      <ResumeUpload />
    </div>
    <div className="setup-footer">
      <ReadinessPanel />
    </div>
  </>
)
