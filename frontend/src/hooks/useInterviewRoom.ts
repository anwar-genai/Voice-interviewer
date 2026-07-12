import { useEffect, useRef, useState } from 'react'
import { Room, RoomEvent, Track } from 'livekit-client'
import type { RemoteTrack } from 'livekit-client'
import { api } from '../lib/api'
import type { Job } from '../lib/types'

export type ConnectionStatus =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'reconnecting' // LiveKit is transparently re-establishing the session
  | 'disconnected'

/** Turn a getUserMedia failure into something a non-technical user can act on. */
function micErrorMessage(err: unknown): string {
  const name = (err as DOMException)?.name
  if (name === 'NotAllowedError' || name === 'SecurityError')
    return 'Microphone access was blocked. Allow the mic for this site in your browser, then try again.'
  if (name === 'NotFoundError' || name === 'OverconstrainedError')
    return 'No microphone was found. Plug one in (or check your system settings) and try again.'
  if (name === 'NotReadableError')
    return 'Your microphone is in use by another app. Close it and try again.'
  return 'Could not start your microphone. Check your browser permissions and try again.'
}

/**
 * Owns the LiveKit room lifecycle for one interview: join-token → connect →
 * publish mic → play the agent's audio, plus mic-permission and reconnection
 * handling. The agent's audio is attached to an in-memory <audio> element so
 * playback never depends on a DOM ref existing at track-subscribe time.
 */
export function useInterviewRoom() {
  const [status, setStatus] = useState<ConnectionStatus>('idle')
  const [isMuted, setIsMuted] = useState(false)
  const [error, setError] = useState('')
  const [interviewId, setInterviewId] = useState('')
  const roomRef = useRef<Room | null>(null)
  const audioElRef = useRef<HTMLAudioElement | null>(null)

  // Disconnect + drop the audio element if the app unmounts mid-interview.
  useEffect(
    () => () => {
      roomRef.current?.disconnect()
      audioElRef.current?.remove()
    },
    [],
  )

  /** Start an interview. Returns the interview id on success; throws otherwise. */
  async function start(job: Job, resume: string, consent: boolean): Promise<string> {
    setError('')
    setStatus('connecting')
    try {
      // Room + identity are derived server-side from the authenticated user.
      const { url, token, interview_id } = await api.joinToken(job, resume, consent)
      setInterviewId(interview_id)

      const room = new Room({
        audioCaptureDefaults: { autoGainControl: true, echoCancellation: true, noiseSuppression: true },
        adaptiveStream: true,
        dynacast: true,
      })
      room.on(RoomEvent.Connected, () => setStatus('connected'))
      room.on(RoomEvent.Reconnecting, () => setStatus('reconnecting'))
      room.on(RoomEvent.Reconnected, () => setStatus('connected'))
      room.on(RoomEvent.Disconnected, () => {
        setStatus((s) => (s === 'idle' ? s : 'disconnected'))
      })
      room.on(RoomEvent.TrackSubscribed, (track: RemoteTrack) => {
        if (track.kind !== Track.Kind.Audio) return
        if (!audioElRef.current) {
          // Must live in the DOM to play reliably — a detached <audio> won't.
          const el = document.createElement('audio')
          el.autoplay = true
          el.style.display = 'none'
          document.body.appendChild(el)
          audioElRef.current = el
        }
        track.attach(audioElRef.current)
        // Sticky activation from the "Start" click lets this play; ignore the
        // promise rejection browsers throw if autoplay is briefly blocked.
        void audioElRef.current.play?.().catch(() => {})
      })

      await room.connect(url, token)

      // Mic permission is the most common first-run failure — handle it loudly.
      try {
        await room.localParticipant.setMicrophoneEnabled(true)
      } catch (micErr) {
        await room.disconnect()
        throw new Error(micErrorMessage(micErr))
      }

      roomRef.current = room
      setIsMuted(false)
      return interview_id
    } catch (err) {
      setStatus('idle')
      const msg = err instanceof Error ? err.message : 'Failed to start interview'
      setError(msg)
      throw new Error(msg)
    }
  }

  async function toggleMute() {
    const room = roomRef.current
    if (!room) return
    const next = !isMuted
    await room.localParticipant.setMicrophoneEnabled(!next)
    setIsMuted(next)
  }

  /** End the interview, tear down the room, and return the id so the caller can score it. */
  async function end(): Promise<string> {
    await roomRef.current?.disconnect()
    roomRef.current = null
    audioElRef.current?.remove()
    audioElRef.current = null
    setStatus('idle')
    return interviewId
  }

  return { status, isMuted, error, interviewId, start, toggleMute, end }
}
