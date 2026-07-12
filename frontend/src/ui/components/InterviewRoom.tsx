import React, { useEffect, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useInterview } from '../InterviewContext'
import { Waveform } from './instruments'

function fmt(total: number): string {
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

/** Route "/interview": the live voice session. */
export const InterviewRoom: React.FC = () => {
  const { room } = useInterview()
  const navigate = useNavigate()
  const [ending, setEnding] = useState(false)
  const [elapsed, setElapsed] = useState(0)

  const live = room.status === 'connected'

  useEffect(() => {
    if (room.status !== 'connected' && room.status !== 'reconnecting') return
    const id = setInterval(() => setElapsed((e) => e + 1), 1000)
    return () => clearInterval(id)
  }, [room.status])

  // A refresh drops the WebRTC session (it can't be resurrected from a URL);
  // there's nothing to show, so go back to setup.
  if (room.status === 'idle') return <Navigate to="/" replace />

  async function end() {
    setEnding(true)
    const id = await room.end()
    navigate(`/feedback/${id}`)
  }

  return (
    <div className="interview-section">
      <div role="status" aria-live="polite">
        {live ? (
          <span className="on-air"><span className="rec" aria-hidden="true" /> Recording <span className="timer">{fmt(elapsed)}</span></span>
        ) : room.status === 'reconnecting' ? (
          <span className="status-badge status-ready">Reconnecting… <span className="timer">{fmt(elapsed)}</span></span>
        ) : room.status === 'disconnected' ? (
          // Also the normal end when the session time limit is reached — not an error.
          <span className="status-badge status-ready">Interview ended</span>
        ) : (
          <span className="status-badge status-ready"><span className="loading-spinner" /> Connecting…</span>
        )}
      </div>

      <h2 className="interview-heading">Your interview is live</h2>
      <p className="interview-sub">Speak naturally — the interviewer is listening and replies when you pause.</p>

      <Waveform live={live} height={150} />

      {room.status === 'reconnecting' && <p className="ready-hint">Connection dropped — reconnecting. Stay on this page.</p>}

      <div className="live-controls">
        <button className={`btn ${room.isMuted ? 'btn-danger' : 'btn-secondary'}`} onClick={room.toggleMute} disabled={!live}>
          {room.isMuted ? 'Unmute' : 'Mute'}
        </button>
        <button className="btn btn-danger" onClick={end} disabled={ending} aria-busy={ending}>
          {ending ? <span className="loading-spinner" /> : null}{' '}
          {room.status === 'disconnected' ? 'Get my feedback' : 'End interview'}
        </button>
      </div>

      <p className="privacy-note">AI interviewer · your live audio isn’t stored after this session ends.</p>
    </div>
  )
}
