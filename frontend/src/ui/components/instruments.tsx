import React, { useEffect, useRef } from 'react'

/**
 * The visual "instruments" of the On-Air identity, shared across screens:
 * a voice waveform (live-animated or static), a VU-meter score gauge, small
 * waveform thumbnails, and a score ring. Canvas access is guarded so these
 * render harmlessly under jsdom (no 2d context) during tests.
 */

function cssv(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

function fit(cv: HTMLCanvasElement): CanvasRenderingContext2D | null {
  const ctx = cv.getContext('2d')
  if (!ctx) return null
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  cv.width = cv.clientWidth * dpr
  cv.height = cv.clientHeight * dpr
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  return ctx
}

function mulberry32(seed: number): () => number {
  let a = seed
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const reduceMotion = () =>
  typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

function paintWave(ctx: CanvasRenderingContext2D, w: number, h: number, rnd: () => number, thick: number) {
  const mid = h / 2
  const bars = Math.max(18, Math.floor(w / 6))
  const gap = w / bars
  const bw = Math.max(1.5, gap * thick)
  const g = ctx.createLinearGradient(0, 0, w, 0)
  g.addColorStop(0, cssv('--accent'))
  g.addColorStop(1, cssv('--warm'))
  ctx.fillStyle = g
  for (let i = 0; i < bars; i++) {
    const env = Math.sin((i / bars) * Math.PI) * 0.55 + 0.45
    const amp = env * (0.35 + rnd() * 0.65) * (h * 0.44) + 2
    const x = i * gap + (gap - bw) / 2
    ctx.beginPath()
    if (ctx.roundRect) ctx.roundRect(x, mid - amp, bw, amp * 2, bw / 2)
    else ctx.rect(x, mid - amp, bw, amp * 2)
    ctx.fill()
  }
}

/** Voice waveform. `live` animates it; otherwise it's a static, seeded shape. */
export const Waveform: React.FC<{ live?: boolean; height?: number; seed?: number }> = ({
  live = false,
  height = 150,
  seed = 7,
}) => {
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const cv = ref.current
    if (!cv) return
    let raf = 0
    const animated = live && !reduceMotion()
    const drawStatic = () => {
      const ctx = fit(cv)
      if (!ctx) return
      ctx.clearRect(0, 0, cv.clientWidth, cv.clientHeight)
      paintWave(ctx, cv.clientWidth, cv.clientHeight, mulberry32(seed), 0.5)
    }
    const frame = (t: number) => {
      const ctx = fit(cv)
      if (!ctx) return
      const w = cv.clientWidth, h = cv.clientHeight, mid = h / 2, bars = 64
      ctx.clearRect(0, 0, w, h)
      const g = ctx.createLinearGradient(0, 0, w, 0)
      g.addColorStop(0, cssv('--accent'))
      g.addColorStop(1, cssv('--warm'))
      ctx.fillStyle = g
      const gap = w / bars, bw = Math.max(2, gap * 0.44)
      for (let i = 0; i < bars; i++) {
        const env = Math.sin((i / bars) * Math.PI)
        const wob = 0.4 + 0.6 * Math.abs(Math.sin(i * 0.5 + t * 0.004) * Math.cos(i * 0.13 + t * 0.002))
        const amp = env * wob * (h * 0.42) + 3
        ctx.beginPath()
        if (ctx.roundRect) ctx.roundRect(i * gap + (gap - bw) / 2, mid - amp, bw, amp * 2, bw / 2)
        else ctx.rect(i * gap + (gap - bw) / 2, mid - amp, bw, amp * 2)
        ctx.fill()
      }
      raf = requestAnimationFrame(frame)
    }
    const onResize = () => { if (!animated) drawStatic() }
    if (animated) raf = requestAnimationFrame(frame)
    else drawStatic()
    window.addEventListener('resize', onResize)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', onResize)
    }
  }, [live, seed])
  return <canvas ref={ref} className="wave-canvas" style={{ height }} aria-hidden="true" />
}

/** A single waveform thumbnail (history cards). */
export const MiniWave: React.FC<{ seed: number }> = ({ seed }) => {
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const cv = ref.current
    if (!cv) return
    const render = () => {
      const ctx = fit(cv)
      if (!ctx) return
      ctx.clearRect(0, 0, cv.clientWidth, cv.clientHeight)
      paintWave(ctx, cv.clientWidth, cv.clientHeight, mulberry32(seed), 0.44)
    }
    render()
    window.addEventListener('resize', render)
    return () => window.removeEventListener('resize', render)
  }, [seed])
  return <canvas ref={ref} className="mini-wave" aria-hidden="true" />
}

/** VU-meter needle gauge for a 0–10 score. */
export const VuMeter: React.FC<{ value: number }> = ({ value }) => {
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const cv = ref.current
    if (!cv) return
    const render = () => {
      const ctx = fit(cv)
      if (!ctx) return
      const w = cv.clientWidth, h = cv.clientHeight
      ctx.clearRect(0, 0, w, h)
      const cx = w / 2, cy = h * 0.92, R = Math.min(w * 0.42, h * 0.82)
      const a0 = Math.PI * 1.16, a1 = Math.PI * 1.84
      const aV = a0 + (Math.max(0, Math.min(10, value)) / 10) * (a1 - a0)
      ctx.lineCap = 'round'
      ctx.lineWidth = Math.max(5, R * 0.14)
      ctx.strokeStyle = cssv('--line')
      ctx.beginPath(); ctx.arc(cx, cy, R, a0, a1); ctx.stroke()
      const g = ctx.createLinearGradient(cx - R, 0, cx + R, 0)
      g.addColorStop(0, cssv('--accent')); g.addColorStop(1, cssv('--warm'))
      ctx.strokeStyle = g
      ctx.beginPath(); ctx.arc(cx, cy, R, a0, aV); ctx.stroke()
      ctx.strokeStyle = cssv('--muted'); ctx.globalAlpha = 0.4; ctx.lineWidth = 1.5
      for (let t = 0; t <= 10; t += 2) {
        const a = a0 + (t / 10) * (a1 - a0)
        ctx.beginPath()
        ctx.moveTo(cx + Math.cos(a) * (R * 1.14), cy + Math.sin(a) * (R * 1.14))
        ctx.lineTo(cx + Math.cos(a) * (R * 1.24), cy + Math.sin(a) * (R * 1.24))
        ctx.stroke()
      }
      ctx.globalAlpha = 1
      ctx.strokeStyle = cssv('--ink'); ctx.lineWidth = 2.4
      ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + Math.cos(aV) * R * 0.94, cy + Math.sin(aV) * R * 0.94); ctx.stroke()
      ctx.fillStyle = cssv('--ink'); ctx.beginPath(); ctx.arc(cx, cy, 3.5, 0, 7); ctx.fill()
    }
    render()
    window.addEventListener('resize', render)
    return () => window.removeEventListener('resize', render)
  }, [value])
  return <canvas ref={ref} className="vu-canvas" aria-hidden="true" />
}

/** Small circular score badge, colored by score band. */
export const ScoreRing: React.FC<{ value: number | null }> = ({ value }) => {
  if (value == null) {
    return (
      <svg className="ring" viewBox="0 0 36 36" aria-hidden="true">
        <circle className="track" cx="18" cy="18" r="15.9" fill="none" strokeWidth="3" />
        <text x="18" y="21.5" textAnchor="middle" fontSize="9" fill="var(--muted)">—</text>
      </svg>
    )
  }
  const pct = Math.max(0, Math.min(10, value)) * 10
  const stroke = value >= 7 ? 'var(--accent)' : value >= 4 ? 'var(--warm)' : 'var(--danger)'
  return (
    <svg className="ring" viewBox="0 0 36 36" aria-hidden="true">
      <circle className="track" cx="18" cy="18" r="15.9" fill="none" strokeWidth="3" />
      <circle
        cx="18" cy="18" r="15.9" fill="none" stroke={stroke} strokeWidth="3" strokeLinecap="round"
        pathLength={100} strokeDasharray={`${pct} 100`} transform="rotate(-90 18 18)"
      />
      <text x="18" y="21.5" textAnchor="middle" fontSize="11">{value}</text>
    </svg>
  )
}
