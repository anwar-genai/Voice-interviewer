import React, { useState } from 'react'

const DISMISS_KEY = 'welcome-dismissed-v1'
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true'

/** First-run intro on the setup screen: what this is, the three steps, and
 *  (in demo mode) a note that the live interviewer is only online on demand. */
export const WelcomeCard: React.FC = () => {
  const [dismissed, setDismissed] = useState(() => localStorage.getItem(DISMISS_KEY) === 'true')
  if (dismissed) return null

  function dismiss() {
    localStorage.setItem(DISMISS_KEY, 'true')
    setDismissed(true)
  }

  return (
    <section className="welcome-card" aria-label="What this is">
      <button className="welcome-close" onClick={dismiss} aria-label="Dismiss introduction">×</button>
      <h2 className="welcome-title">Practice a real spoken job interview</h2>
      <p className="welcome-lede">
        An AI interviewer talks with you by voice, then scores your performance with
        specific, coaching-style feedback. Bring headphones and a quiet spot.
      </p>
      <ol className="welcome-steps">
        <li><strong>Add the role</strong> — paste a job description.</li>
        <li><strong>Talk it through</strong> — answer the interviewer out loud, just like the real thing.</li>
        <li><strong>Get feedback</strong> — a scored report on strengths and what to improve.</li>
      </ol>
      {DEMO_MODE && (
        <p className="welcome-demo" role="note">
          <span className="welcome-demo-dot" aria-hidden="true" />
          This is a live demo: the AI interviewer runs during scheduled sessions.
          If a session isn&rsquo;t live, the interview won&rsquo;t connect — reach out to arrange a time.
        </p>
      )}
    </section>
  )
}
