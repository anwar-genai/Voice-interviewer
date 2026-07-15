// Thin typed wrappers over authedFetch. Consolidates the "check res.ok, pull
// `detail`, throw a friendly Error" boilerplate that was copy-pasted across the
// old god-component. No caching/retry layer here on purpose — scoring retry is
// idempotent server-side, and a single user doesn't need React Query yet.
// ponytail: plain fetch; add React Query in Phase 6/7 when there's real traffic.
import { authedFetch } from './supabase'
import type { Job, Feedback, InterviewSummary, InterviewDetail, SharedReport } from './types'

async function json<T>(resP: Promise<Response>, fallbackMsg: string): Promise<T> {
  const res = await resP
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body?.detail || fallbackMsg)
  }
  return res.json() as Promise<T>
}

const jsonInit = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  parseJobText: (text: string) =>
    json<Job>(authedFetch('/utils/parse-job-text-llm', jsonInit({ text })), 'Failed to extract job information'),

  uploadResume(file: File): Promise<string> {
    const form = new FormData()
    form.append('file', file)
    return json<{ text: string }>(
      authedFetch('/utils/parse-pdf-upload', { method: 'POST', body: form }),
      'Failed to parse resume',
    ).then((d) => d.text)
  },

  joinToken: (job: Job, resume: string, consent: boolean) =>
    json<{ url: string; token: string; interview_id: string }>(
      authedFetch('/agent/join-token', jsonInit({ job, resume, consent })),
      'Failed to start interview',
    ),

  generateFeedback: (interview_id: string) =>
    json<Feedback>(authedFetch('/feedback/generate', jsonInit({ interview_id })), 'Failed to generate feedback'),

  getFeedback: (id: string) =>
    json<Feedback>(authedFetch(`/feedback/${id}`), 'This interview has not been scored yet.'),

  listInterviews: () =>
    json<InterviewSummary[]>(authedFetch('/interviews'), 'Failed to load history'),

  getInterview: (id: string) =>
    json<InterviewDetail>(authedFetch(`/interviews/${id}`), 'Failed to load that interview'),

  deleteAllInterviews: () =>
    json<{ deleted: number }>(authedFetch('/interviews', { method: 'DELETE' }), 'Failed to delete your data'),

  shareInterview: (id: string) =>
    json<{ token: string }>(authedFetch(`/interviews/${id}/share`, { method: 'POST' }), 'Failed to create the share link'),

  unshareInterview: (id: string) =>
    json<{ shared: boolean }>(authedFetch(`/interviews/${id}/share`, { method: 'DELETE' }), 'Failed to stop sharing'),

  // Public — works logged out; authedFetch just skips the header without a session.
  getSharedReport: (token: string) =>
    json<SharedReport>(authedFetch(`/share/${token}`), 'This shared report does not exist or was unshared.'),
}
