import React, { createContext, useContext, useState } from 'react'
import { useInterviewRoom } from '../hooks/useInterviewRoom'
import type { Job } from '../lib/types'

/**
 * The live interview spans two routes (/ setup → /interview). The job/resume/
 * consent the user assembles and the LiveKit session must outlive those route
 * changes, so they live here rather than in any single screen.
 */
type InterviewCtx = {
  job: Job | null
  setJob: (j: Job | null) => void
  resume: string
  setResume: (r: string) => void
  consent: boolean
  setConsent: (c: boolean) => void
  room: ReturnType<typeof useInterviewRoom>
  /** Clear everything for a fresh interview. */
  reset: () => void
  /** Prefill job + resume from a past interview (retake); consent is re-asked. */
  prefill: (job: Job | null, resume: string) => void
}

const Ctx = createContext<InterviewCtx | null>(null)

export const InterviewProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [job, setJob] = useState<Job | null>(null)
  const [resume, setResume] = useState('')
  const [consent, setConsent] = useState(false)
  const room = useInterviewRoom()

  const reset = () => {
    setJob(null)
    setResume('')
    setConsent(false)
  }
  const prefill = (j: Job | null, r: string) => {
    setJob(j)
    setResume(r)
    setConsent(false)
  }

  return (
    <Ctx.Provider value={{ job, setJob, resume, setResume, consent, setConsent, room, reset, prefill }}>
      {children}
    </Ctx.Provider>
  )
}

export function useInterview(): InterviewCtx {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useInterview must be used inside <InterviewProvider>')
  return ctx
}
