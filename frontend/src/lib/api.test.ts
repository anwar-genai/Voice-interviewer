/**
 * Exercises the real api.ts helper (only authedFetch is mocked), so the
 * "await the Response promise" contract can't silently regress — the component
 * tests mock `api` wholesale and would miss it.
 */
import { expect, it, vi, beforeEach } from 'vitest'

const authedFetch = vi.hoisted(() => vi.fn())
vi.mock('./supabase', () => ({ authedFetch }))

import { api } from './api'

const asResponse = (body: unknown, ok = true) =>
  ({ ok, json: () => Promise.resolve(body) }) as unknown as Response

beforeEach(() => authedFetch.mockReset())

it('resolves the parsed JSON body on success', async () => {
  authedFetch.mockResolvedValue(asResponse({ job_title: 'Nurse' }))
  await expect(api.parseJobText('some posting')).resolves.toEqual({ job_title: 'Nurse' })
})

it('throws the server-provided detail on error', async () => {
  authedFetch.mockResolvedValue(asResponse({ detail: 'Posting was empty' }, false))
  await expect(api.parseJobText('')).rejects.toThrow('Posting was empty')
})
