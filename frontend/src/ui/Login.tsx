import React, { useState } from 'react'
import { supabase } from '../lib/supabase'

/** Landing + sign-in gate for logged-out visitors: a value-prop hero on the
 *  left, a booth-style product preview on the right. */
export const Login: React.FC = () => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')

  async function tryDemo() {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      // Anonymous Supabase session: a real JWT, so the whole app works unchanged.
      const { error } = await supabase.auth.signInAnonymously()
      if (error) throw error
    } catch (err: any) {
      setError(err.message ?? 'Could not start the demo')
      setBusy(false)
    }
  }

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
    <div className="landing">
      <nav className="landing-nav" aria-label="Brand">
        <span className="app-title"><span className="brand-dot" aria-hidden="true" /> AI Interview Coach</span>
      </nav>

      <div className="landing-grid">
        <section className="landing-copy">
          <span className="landing-eyebrow">Voice mock interviews</span>
          <h1 className="landing-headline">Practice the interview <em>out loud</em>.</h1>
          <p className="landing-lede">
            A live AI interviewer talks with you by voice, adapts to the role and your
            résumé, then scores your answers with specific, coaching-style feedback.
          </p>

          <form className="auth-card landing-auth" onSubmit={submit}>
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
            <button className="btn btn-primary btn-full btn-lg" type="submit" disabled={busy}>
              {busy ? <span className="loading-spinner" /> : mode === 'signin' ? 'Sign in' : 'Start free →'}
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-full"
              onClick={() => setMode(mode === 'signin' ? 'signup' : 'signin')}
            >
              {mode === 'signin' ? 'Need an account? Sign up' : 'Have an account? Sign in'}
            </button>
            <button type="button" className="btn btn-secondary btn-full" onClick={tryDemo} disabled={busy}>
              Try a live demo — no signup
            </button>
            {notice && <div className="status-badge status-ready">{notice}</div>}
            {error && <div className="status-badge status-error">⚠️ {error}</div>}
          </form>

          <p className="landing-trust">No credit card. Your practice, your data — deletable anytime.</p>
        </section>

        <aside className="booth-preview" aria-hidden="true">
          <div className="booth-top">
            <span className="booth-onair"><span className="booth-onair-dot" /> ON AIR</span>
            <span className="booth-timer">04:12</span>
          </div>
          <p className="booth-question">
            “Tell me about a time you had to make a decision without complete information.”
          </p>
          <div className="booth-wave">
            {Array.from({ length: 28 }).map((_, i) => (
              <span key={i} className="booth-bar" style={{ animationDelay: `${(i % 7) * 0.09}s` }} />
            ))}
          </div>
          <div className="booth-foot">
            <span className="booth-mic" /> Listening…
            <span className="booth-score">
              <span className="booth-ring" /> 8.4
            </span>
          </div>
        </aside>
      </div>

      <section className="landing-how" aria-label="How it works">
        {[
          ['01', 'Add the role', 'Paste a job description — the interviewer adapts to it and your résumé.'],
          ['02', 'Talk it through', 'A live voice interview, out loud, just like the real thing.'],
          ['03', 'Get feedback', 'A scored report: strengths, gaps, and what to fix before the real one.'],
        ].map(([n, title, detail]) => (
          <div className="how-step" key={n}>
            <span className="how-n">{n}</span>
            <h3 className="how-t">{title}</h3>
            <p className="how-d">{detail}</p>
          </div>
        ))}
      </section>
    </div>
  )
}
