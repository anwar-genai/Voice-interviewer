/**
 * Smoke test: the app shell renders in both auth states without touching
 * Supabase or the network (the auth client is mocked at the module boundary).
 */
import React from 'react'
import { render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'

const state: { session: unknown } = { session: null }

vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: () => Promise.resolve({ data: { session: state.session } }),
      onAuthStateChange: () => ({ data: { subscription: { unsubscribe() {} } } }),
      signOut: () => Promise.resolve({ error: null }),
    },
  },
  authedFetch: vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve([]) })),
}))

import { App } from './App'

it('shows the login gate when signed out', async () => {
  state.session = null
  render(<App />)
  expect(await screen.findByText(/sign in to practice/i)).toBeTruthy()
})

it('shows the interview app when signed in', async () => {
  state.session = { user: { id: 'u1' }, access_token: 't' }
  render(<App />)
  expect(await screen.findByText(/AI Interview Coach/i)).toBeTruthy()
  expect(screen.queryByText(/sign in to practice/i)).toBeNull()
})
