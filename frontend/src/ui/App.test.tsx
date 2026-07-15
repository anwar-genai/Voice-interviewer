/**
 * Smoke test: the app shell renders in both auth states without touching
 * Supabase or the network (the auth client is mocked at the module boundary).
 */
import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { expect, it, vi } from 'vitest'

const state: { session: unknown } = { session: null }
const signInAnonymously = vi.hoisted(() => vi.fn(() => Promise.resolve({ data: {}, error: null })))

vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: () => Promise.resolve({ data: { session: state.session } }),
      onAuthStateChange: () => ({ data: { subscription: { unsubscribe() {} } } }),
      signOut: () => Promise.resolve({ error: null }),
      signInAnonymously,
    },
  },
  authedFetch: vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve([]) })),
}))

import { App } from './App'

it('shows the login gate when signed out', async () => {
  state.session = null
  render(<App />)
  expect(await screen.findByText(/no credit card/i)).toBeTruthy()
  expect(screen.getByText(/talk it through/i)).toBeTruthy() // how-it-works strip lives here now
})

it('starts an anonymous session from the demo button', async () => {
  state.session = null
  render(<App />)
  fireEvent.click(await screen.findByText(/try a live demo/i))
  expect(signInAnonymously).toHaveBeenCalledOnce()
})

it('shows the interview app when signed in', async () => {
  state.session = { user: { id: 'u1' }, access_token: 't' }
  render(<App />)
  expect(await screen.findByText(/AI Interview Coach/i)).toBeTruthy()
  expect(screen.queryByText(/no credit card/i)).toBeNull()
})
