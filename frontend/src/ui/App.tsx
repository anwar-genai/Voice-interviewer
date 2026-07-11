import React, { useState, useEffect, useRef } from 'react'
import { Room, RoomEvent, Track, RemoteTrack, RemoteParticipant } from 'livekit-client'
import type { Session } from '@supabase/supabase-js'
import { supabase, authedFetch } from '../lib/supabase'
import { Login } from './Login'
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
  if (!session) return <Login />
  return <InterviewApp onSignOut={() => supabase.auth.signOut()} />
}

const InterviewApp: React.FC<{ onSignOut: () => void }> = ({ onSignOut }) => {
  // Input states
  const [jobUrl, setJobUrl] = useState('')
  const [jobText, setJobText] = useState('')
  const [resumeFile, setResumeFile] = useState<File | null>(null)
  
  // Parsed data
  const [job, setJob] = useState<any>(null)
  const [resume, setResume] = useState<string>('')
  
  // UI states
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>('')
  const [activeStep, setActiveStep] = useState<'input' | 'interview'>('input')
  
  // LiveKit states
  const [room, setRoom] = useState<Room | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [isMuted, setIsMuted] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [consent, setConsent] = useState(false)
  const audioRef = useRef<HTMLAudioElement>(null)

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (room) {
        room.disconnect()
      }
    }
  }, [room])

  async function parseJobUrl() {
    if (!jobUrl.trim()) return
    setLoading(true)
    setError('')
    try {
      const res = await authedFetch('/utils/parse-link-llm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: jobUrl })
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to parse job URL')
      }
      const data = await res.json()
      setJob(data)
    } catch (err: any) {
      setError(err.message)
      // If URL parsing fails, suggest using text
      if (err.message.includes('not accessible')) {
        setError('Cannot access this URL. Please copy and paste the job description instead.')
      }
    } finally {
      setLoading(false)
    }
  }

  async function parseJobTextLLM() {
    if (!jobText.trim()) return
    setLoading(true)
    setError('')
    try {
      const res = await authedFetch('/utils/parse-job-text-llm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: jobText })
      })
      if (!res.ok) throw new Error('Failed to extract job information')
      const data = await res.json()
      setJob(data)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function uploadResume(file: File | null = resumeFile) {
    if (!file) return
    setLoading(true)
    setError('')
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await authedFetch('/utils/parse-pdf-upload', {
        method: 'POST',
        body: form
      })
      if (!res.ok) throw new Error('Failed to parse resume')
      const data = await res.json()
      setResume(data.text)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function startInterview() {
    if (!job || !resume || !consent) return

    setLoading(true)
    setError('')

    try {
      // Room and identity are derived server-side from the authenticated user.
      const tokenRes = await authedFetch('/agent/join-token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job, resume, consent })
      })

      if (!tokenRes.ok) throw new Error('Failed to start interview')
      const { url, token } = await tokenRes.json()
      
      // Connect to LiveKit room
      const newRoom = new Room({
        audioCaptureDefaults: {
          autoGainControl: true,
          echoCancellation: true,
          noiseSuppression: true,
        },
        adaptiveStream: true,
        dynacast: true,
      })
      
      // Set up event handlers
      newRoom.on(RoomEvent.Connected, () => {
        console.log('Connected to room')
        setIsConnected(true)
        setIsRecording(true)
      })
      
      newRoom.on(RoomEvent.Disconnected, () => {
        console.log('Disconnected from room')
        setIsConnected(false)
        setIsRecording(false)
      })
      
      newRoom.on(RoomEvent.TrackSubscribed, (track: RemoteTrack, publication, participant: RemoteParticipant) => {
        console.log('Track subscribed:', track.kind)
        if (track.kind === Track.Kind.Audio && audioRef.current) {
          track.attach(audioRef.current)
        }
      })
      
      // Connect to room
      await newRoom.connect(url, token)
      
      // Publish microphone
      await newRoom.localParticipant.setMicrophoneEnabled(true)
      
      setRoom(newRoom)
      setActiveStep('interview')

      // The agent worker uses automatic dispatch: it joins this room on its own
      // and reads the job/resume we stored in the room metadata (via /agent/join-token).

    } catch (err: any) {
      setError(err.message)
      console.error('Failed to start interview:', err)
    } finally {
      setLoading(false)
    }
  }

  async function toggleMute() {
    if (!room) return
    const newMuted = !isMuted
    await room.localParticipant.setMicrophoneEnabled(!newMuted)
    setIsMuted(newMuted)
  }

  async function endInterview() {
    if (room) {
      await room.disconnect()
      setRoom(null)
      setIsConnected(false)
      setActiveStep('input')
    }
  }

  const canStartInterview = job && resume && consent && !loading

  return (
    <div className="app-container">
      <header className="app-header">
        <h1 className="app-title">🎤 AI Interview Coach</h1>
        <p className="app-subtitle">Practice your interview skills with an AI-powered mock interviewer</p>
        <button className="btn sign-out" onClick={onSignOut}>
          Sign out
        </button>
      </header>

      <main className="main-content">
        {activeStep === 'input' ? (
          <div className="steps-container">
            {/* Step 1: Job Information */}
            <div className="step-section">
              <div className="step-header">
                <div className="step-number">1</div>
                <h2 className="step-title">Job Information</h2>
              </div>

              <div className="input-group">
                <label className="input-label">Job URL</label>
                <input
                  type="url"
                  className="input-field"
                  placeholder="https://example.com/job-posting"
                  value={jobUrl}
                  onChange={(e) => setJobUrl(e.target.value)}
                />
                <button 
                  className="btn btn-primary btn-full"
                  onClick={parseJobUrl}
                  disabled={!jobUrl.trim() || loading}
                >
                  {loading ? <span className="loading-spinner" /> : '🔍'} Parse Job URL
                </button>
              </div>

              <div className="or-divider">
                <span>OR</span>
              </div>

              <div className="input-group">
                <label className="input-label">Paste Job Description</label>
                <textarea
                  className="textarea-field"
                  placeholder="Copy and paste the job description here..."
                  value={jobText}
                  onChange={(e) => setJobText(e.target.value)}
                />
                <button 
                  className="btn btn-primary btn-full"
                  onClick={parseJobTextLLM}
                  disabled={!jobText.trim() || loading}
                >
                  {loading ? <span className="loading-spinner" /> : '✨'} Extract with AI
                </button>
              </div>

              {job && (
                <div className="preview-section">
                  <h3 className="preview-title">📋 Parsed Job Details</h3>
                  <div className="preview-content">
                    {JSON.stringify(job, null, 2)}
                  </div>
                </div>
              )}
            </div>

            {/* Step 2: Resume */}
            <div className="step-section">
              <div className="step-header">
                <div className="step-number">2</div>
                <h2 className="step-title">Your Resume</h2>
              </div>

              <div className="input-group">
                <label className="input-label">Upload Resume (PDF)</label>
                <div className="file-upload">
                  <input
                    type="file"
                    id="resume-upload"
                    accept="application/pdf"
                    onChange={(e) => {
                      const file = e.target.files?.[0]
                      if (file) {
                        setResumeFile(file)
                        setResume('')
                        uploadResume(file)
                      }
                    }}
                  />
                  <label 
                    htmlFor="resume-upload" 
                    className={`file-upload-label ${resumeFile ? 'has-file' : ''}`}
                  >
                    {resumeFile ? `📄 ${resumeFile.name}` : '📁 Choose PDF file'}
                  </label>
                </div>
                {resumeFile && loading && !resume && (
                  <div className="status-badge status-ready">
                    <span className="loading-spinner" /> Parsing your resume…
                  </div>
                )}
                {resume && (
                  <div className="status-badge status-connected">
                    ✅ Resume parsed
                  </div>
                )}
              </div>

              {resume && (
                <div className="preview-section">
                  <h3 className="preview-title">📝 Resume Content</h3>
                  <div className="preview-content">
                    {resume.substring(0, 500)}...
                  </div>
                </div>
              )}

              {error && (
                <div className="status-badge status-error">
                  ⚠️ {error}
                </div>
              )}

              <div className="ready-panel">
                <div className="ready-checklist">
                  <span className={job ? 'ready-item done' : 'ready-item'}>
                    {job ? '✅' : '⬜'} Job details
                  </span>
                  <span className={resume ? 'ready-item done' : 'ready-item'}>
                    {resume ? '✅' : '⬜'} Resume
                  </span>
                </div>
                <label
                  className="ready-hint"
                  style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start', cursor: 'pointer', marginBottom: '0.75rem' }}
                >
                  <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
                  <span>
                    I consent to voice recording and resume processing for this AI mock interview.
                    The interviewer and feedback are AI-generated.
                  </span>
                </label>
                <button
                  className="btn btn-success btn-full"
                  onClick={startInterview}
                  disabled={!canStartInterview}
                  style={{ fontSize: '1.15rem', padding: '1rem 2rem' }}
                >
                  {loading && job && resume ? <span className="loading-spinner" /> : '🚀'} Start Mock Interview
                </button>
                {!canStartInterview && !loading && (
                  <p className="ready-hint">
                    {!job && !resume
                      ? 'Add a job description and upload your resume to begin.'
                      : !job
                        ? 'Add a job description above to continue.'
                        : !resume
                          ? 'Upload your resume above to continue.'
                          : 'Check the consent box above to begin.'}
                  </p>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="interview-section">
            <div className={`status-badge ${isConnected ? 'status-connected' : 'status-ready'}`}>
              {isConnected ? '🟢 Connected' : '🟡 Connecting...'}
            </div>

            <h2 style={{ fontSize: '2rem', marginBottom: '1rem' }}>
              Mock Interview in Progress
            </h2>
            <p style={{ color: '#6b7280', marginBottom: '2rem' }}>
              Speak clearly into your microphone. The AI interviewer will respond to you.
            </p>

            {isRecording && (
              <div className="audio-indicator">
                <span>🎙️ Recording</span>
                <div className="audio-bars">
                  <div className="audio-bar"></div>
                  <div className="audio-bar"></div>
                  <div className="audio-bar"></div>
                  <div className="audio-bar"></div>
                  <div className="audio-bar"></div>
                </div>
              </div>
            )}

            <div className="interview-controls">
              <button 
                className={`btn ${isMuted ? 'btn-danger' : 'btn-secondary'}`}
                onClick={toggleMute}
              >
                {isMuted ? '🔇 Unmute' : '🔊 Mute'}
              </button>
              <button 
                className="btn btn-danger"
                onClick={endInterview}
              >
                ⏹️ End Interview
              </button>
            </div>

            <audio ref={audioRef} autoPlay />
          </div>
        )}
      </main>
    </div>
  )
}