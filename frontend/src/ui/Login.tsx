import React, { useState } from 'react'
import { supabase } from '../lib/supabase'

/** Minimal email + password sign-in / sign-up gate. Phase 5 will flesh out the UX. */
export const Login: React.FC = () => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    setNotice('')
    try {
      // Call as methods so the auth client keeps its `this` binding (a detached
      // reference throws "Cannot read properties of undefined (reading 'storage')").
      const { error } =
        mode === 'signin'
          ? await supabase.auth.signInWithPassword({ email, password })
          : await supabase.auth.signUp({ email, password })
      if (error) throw error
      if (mode === 'signup') setNotice('Check your email to confirm your account, then sign in.')
    } catch (err: any) {
      setError(err.message ?? 'Authentication failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="app-container">
      <header className="app-header">
        <h1 className="app-title">🎤 AI Interview Coach</h1>
        <p className="app-subtitle">Sign in to practice your interview skills</p>
      </header>
      <main className="main-content">
        <form className="auth-card" onSubmit={submit}>
          <div className="input-group">
            <label className="input-label">Email</label>
            <input
              type="email"
              className="input-field"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="input-group">
            <label className="input-label">Password</label>
            <input
              type="password"
              className="input-field"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button className="btn btn-primary btn-full" type="submit" disabled={busy}>
            {busy ? <span className="loading-spinner" /> : mode === 'signin' ? 'Sign in' : 'Create account'}
          </button>
          <button
            type="button"
            className="btn btn-secondary btn-full"
            onClick={() => setMode(mode === 'signin' ? 'signup' : 'signin')}
            style={{ marginTop: '0.5rem' }}
          >
            {mode === 'signin' ? 'Need an account? Sign up' : 'Have an account? Sign in'}
          </button>
          {notice && <div className="status-badge status-ready">{notice}</div>}
          {error && <div className="status-badge status-error">⚠️ {error}</div>}
        </form>
      </main>
    </div>
  )
}
