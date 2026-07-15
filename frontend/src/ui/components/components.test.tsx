/**
 * Component tests for the Phase 5 structure. The API layer is mocked at the
 * module boundary so nothing touches Supabase, LiveKit, or the network.
 */
import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { expect, it, vi, beforeEach } from 'vitest'

// vi.hoisted runs before the hoisted vi.mock factory, so `api` is initialized in time.
const api = vi.hoisted(() => ({
  deleteAllInterviews: vi.fn(),
  getFeedback: vi.fn(),
  generateFeedback: vi.fn(),
  getInterview: vi.fn(),
  listInterviews: vi.fn(),
  joinToken: vi.fn(),
  shareInterview: vi.fn(),
  unshareInterview: vi.fn(),
  getSharedReport: vi.fn(),
}))
vi.mock('../../lib/api', () => ({ api }))

import { InterviewProvider } from '../InterviewContext'
import { Settings } from './Settings'
import { FeedbackReport } from './FeedbackReport'
import { SharedReport } from './SharedReport'
import { History } from './History'
import { JobPreview } from './JobPreview'

const wrap = (ui: React.ReactNode, path = '/') => (
  <MemoryRouter initialEntries={[path]}>
    <InterviewProvider>{ui}</InterviewProvider>
  </MemoryRouter>
)

beforeEach(() => {
  Object.values(api).forEach((fn) => fn.mockReset())
})

it('Settings deletes all data only after an explicit confirm', async () => {
  api.deleteAllInterviews.mockResolvedValue({ deleted: 3 })
  render(wrap(<Settings />))

  // First click just arms the confirmation — nothing deleted yet.
  fireEvent.click(screen.getByText('Delete all my data'))
  expect(api.deleteAllInterviews).not.toHaveBeenCalled()

  fireEvent.click(screen.getByText('Yes, delete everything'))
  expect(await screen.findByText(/Deleted 3 interviews/i)).toBeTruthy()
  expect(api.deleteAllInterviews).toHaveBeenCalledOnce()
})

it('FeedbackReport shows the stored score without regenerating it', async () => {
  api.getFeedback.mockResolvedValue({
    strengths: ['clear answers'], improvements: [], recommendations: [],
    overall_score: 8, technical_score: 7, communication_score: 9,
  })
  api.getInterview.mockResolvedValue({ id: 'x', job: {}, resume: '', turns: [] })

  render(wrap(<Routes><Route path="/feedback/:id" element={<FeedbackReport />} /></Routes>, '/feedback/x'))

  expect(await screen.findByLabelText(/Overall score 8 out of 10/i)).toBeTruthy()
  expect(api.generateFeedback).not.toHaveBeenCalled()
})

it('FeedbackReport generates the score when none is stored yet', async () => {
  api.getFeedback.mockRejectedValue(new Error('not scored yet'))
  api.generateFeedback.mockResolvedValue({
    strengths: [], improvements: ['go deeper'], recommendations: [],
    overall_score: 5, technical_score: 5, communication_score: 5,
  })
  api.getInterview.mockResolvedValue({ id: 'x', job: {}, resume: '', turns: [] })

  render(wrap(<Routes><Route path="/feedback/:id" element={<FeedbackReport />} /></Routes>, '/feedback/x'))

  await waitFor(() => expect(api.generateFeedback).toHaveBeenCalledOnce())
  expect(await screen.findByLabelText(/Overall score 5 out of 10/i)).toBeTruthy()
})

it('History shows score-appropriate actions per interview', async () => {
  api.listInterviews.mockResolvedValue([
    { id: 'a', status: 'completed', job_title: 'Nurse', overall_score: 8, created_at: '2026-07-12T18:40:00Z' },
    { id: 'b', status: 'completed', job_title: 'Ward Manager', overall_score: null, created_at: '2026-07-09T20:05:00Z' },
  ])
  render(wrap(<History />))

  expect(await screen.findByText('Nurse')).toBeTruthy()
  expect(screen.getByText('View feedback')).toBeTruthy() // scored → view
  expect(screen.getByText('Score')).toBeTruthy() // unscored but conducted → score
})

it('History charts score progress oldest-first, skipping unscored interviews', async () => {
  // API returns newest first; the chart must re-sort ascending and drop the null.
  api.listInterviews.mockResolvedValue([
    { id: 'c', status: 'completed', job_title: 'Nurse', overall_score: null, created_at: '2026-07-12T10:00:00Z' },
    { id: 'b', status: 'completed', job_title: 'Nurse', overall_score: 8, created_at: '2026-07-10T10:00:00Z' },
    { id: 'a', status: 'completed', job_title: 'Nurse', overall_score: 5, created_at: '2026-07-01T10:00:00Z' },
  ])
  render(wrap(<History />))
  expect(await screen.findByRole('img', { name: /oldest to newest: 5, 8 out of 10/ })).toBeTruthy()
})

it('History hides the trend chart with fewer than two scored interviews', async () => {
  api.listInterviews.mockResolvedValue([
    { id: 'a', status: 'completed', job_title: 'Nurse', overall_score: 8, created_at: '2026-07-12T10:00:00Z' },
  ])
  render(wrap(<History />))
  expect(await screen.findByText('Nurse')).toBeTruthy()
  expect(screen.queryByRole('img', { name: /oldest to newest/ })).toBeNull()
})

it('FeedbackReport mints a share link on demand', async () => {
  api.getFeedback.mockResolvedValue({
    strengths: [], improvements: [], recommendations: [],
    overall_score: 8, technical_score: 7, communication_score: 9,
  })
  api.getInterview.mockResolvedValue({ id: 'x', job: {}, resume: '', turns: [], share_token: null })
  api.shareInterview.mockResolvedValue({ token: 'tok123' })

  render(wrap(<Routes><Route path="/feedback/:id" element={<FeedbackReport />} /></Routes>, '/feedback/x'))

  fireEvent.click(await screen.findByText('Share this report'))
  expect(await screen.findByText(/\/s\/tok123/)).toBeTruthy()
  expect(screen.getByText('Stop sharing')).toBeTruthy()
  expect(api.shareInterview).toHaveBeenCalledWith('x')
})

it('SharedReport renders a public report from just a token', async () => {
  api.getSharedReport.mockResolvedValue({
    job_title: 'Backend Engineer', created_at: '2026-07-12T18:40:00Z',
    feedback: {
      strengths: ['clear answers'], improvements: [], recommendations: [],
      overall_score: 8, technical_score: 7, communication_score: 9,
    },
  })
  render(
    <MemoryRouter initialEntries={['/s/tok123']}>
      <Routes><Route path="/s/:token" element={<SharedReport />} /></Routes>
    </MemoryRouter>,
  )
  expect(await screen.findByText(/Backend Engineer/)).toBeTruthy()
  expect(screen.getByText('clear answers')).toBeTruthy()
  expect(api.getSharedReport).toHaveBeenCalledWith('tok123')
})

it('JobPreview keeps long fields collapsed until expanded', () => {
  render(<JobPreview job={{ job_title: 'Nurse', responsibilities: 'Triage patients and manage the ED floor.' }} />)
  expect(screen.getByText('Nurse')).toBeTruthy()
  expect(screen.queryByText(/Triage patients/)).toBeNull()
  fireEvent.click(screen.getByText(/Show full details/))
  expect(screen.getByText(/Triage patients/)).toBeTruthy()
})
