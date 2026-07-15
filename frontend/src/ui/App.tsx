import React, { useState, useEffect, useRef } from 'react'
import { BrowserRouter, Routes, Route, Navigate, NavLink, useLocation } from 'react-router-dom'
import type { Session } from '@supabase/supabase-js'
import { supabase } from '../lib/supabase'
import { Login } from './Login'
import { InterviewProvider } from './InterviewContext'
import { SetupScreen } from './components/SetupScreen'
import { InterviewRoom } from './components/InterviewRoom'
import { FeedbackReport } from './components/FeedbackReport'
import { SharedReport } from './components/SharedReport'
import { History } from './components/History'
import { Settings } from './components/Settings'
import './App.css'

export const App: React.FC = () => {
  const [session, setSession] = useState<Session | null>(null)
  const [authReady, setAuthReady] = useState(false)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setAuthReady(true)
    })
    const { data: sub } = supabase.auth.onAuthStateChange((_event, s) => setSession(s))
    return () => sub.subscription.unsubscribe()
  }, [])

  if (!authReady) return null

  // /s/:token is public (shared feedback reports); everything else sits behind auth.
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/s/:token" element={<SharedReport />} />
        <Route
          path="*"
          element={
            session ? (
              <AuthedApp email={session.user?.email} guest={Boolean(session.user?.is_anonymous)} />
            ) : (
              <Login />
            )
          }
        />
      </Routes>
    </BrowserRouter>
  )
}

const AuthedApp: React.FC<{ email?: string; guest: boolean }> = ({ email, guest }) => (
  <InterviewProvider>
    <Header onSignOut={() => supabase.auth.signOut()} email={email} guest={guest} />
    <div className="app-container">
      <main className="main-content">
        <Routes>
          <Route path="/" element={<SetupScreen guest={guest} />} />
          <Route path="/interview" element={<InterviewRoom />} />
          <Route path="/feedback/:id" element={<FeedbackReport />} />
          <Route path="/history" element={<History />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  </InterviewProvider>
)

const Header: React.FC<{ onSignOut: () => void; email?: string; guest: boolean }> = ({ onSignOut, email, guest }) => {
  // Hide the whole nav during the live session — you shouldn't navigate away
  // (or sign out) mid-interview.
  const inInterview = useLocation().pathname === '/interview'
  return (
    <header className="app-header">
      <div className="nav-inner">
        <NavLink to="/" className="app-title">
          <span className="brand-dot" aria-hidden="true" /> AI Interview Coach
        </NavLink>
        {!inInterview && (
          <nav className="app-nav" aria-label="Main">
            <NavLink to="/" end className="nav-link">New interview</NavLink>
            <NavLink to="/history" className="nav-link">History</NavLink>
            <AccountMenu email={email} guest={guest} onSignOut={onSignOut} />
          </nav>
        )}
      </div>
    </header>
  )
}

const AccountMenu: React.FC<{ email?: string; guest?: boolean; onSignOut: () => void }> = ({ email, guest, onSignOut }) => {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  return (
    <div className="account" ref={ref}>
      <button
        className="avatar-btn"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
        title={guest ? 'Guest session' : email}
        onClick={() => setOpen((v) => !v)}
      >
        {guest ? 'G' : (email?.[0] || '?').toUpperCase()}
      </button>
      {open && (
        <div className="menu-panel" role="menu">
          {(guest || email) && <div className="menu-email">{guest ? 'Guest demo session' : email}</div>}
          {guest && (
            <button role="menuitem" className="menu-item" onClick={() => { setOpen(false); onSignOut() }}>
              Create a free account
            </button>
          )}
          <NavLink to="/settings" role="menuitem" className="menu-item" onClick={() => setOpen(false)}>Privacy &amp; data</NavLink>
          <button role="menuitem" className="menu-item" onClick={() => { setOpen(false); onSignOut() }}>
            {guest ? 'Exit demo' : 'Sign out'}
          </button>
        </div>
      )}
    </div>
  )
}
