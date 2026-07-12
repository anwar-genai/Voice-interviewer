# Phase 5 — Frontend Maturity

What shipped, what was genuinely hard, and what I'd improve. Companion to
`ROADMAP.md` Phase 5.

## What shipped

The roadmap's bar: no god-component, no `any`, failures handled gracefully, and
users can see/withdraw consent and delete their data.

- **Decomposition** — the 380-line `App.tsx` is now an auth gate + router shell.
  The flow lives in small components (`JobInput`, `ResumeUpload`, `ReadinessPanel`,
  `SetupScreen`, `InterviewRoom`, `FeedbackReport`, `History`, `Settings`,
  `JobPreview`), a `useInterviewRoom` hook that owns the LiveKit lifecycle, and an
  `InterviewProvider` context holding the job/résumé/consent + live session across
  routes.
- **Routing (React Router)** — `/`, `/interview`, `/feedback/:id`, `/history`,
  `/settings` are real URLs: refresh-safe, back-button works, feedback reports are
  shareable. `/interview` redirects home on refresh (a WebRTC session can't be
  resurrected from a URL). The whole nav is hidden during a live interview.
- **Typed, no `any`** — hand-written `Job`/`Feedback`/`Interview*` types mirroring the
  backend Pydantic models. Skipped an OpenAPI codegen pipeline as more machinery than a
  seven-field object warrants (`ponytail:` noted).
- **Graceful failures** — explicit mic-permission messages (denied / no device / in use),
  and surfaced `Reconnecting`/`Disconnected` states instead of a silent dead session.
- **Privacy + transparency** — consent stays per-interview; a `/settings` screen offers
  a confirm-gated **delete-all-my-data** wired to `DELETE /interviews`, plus plain-language
  "how this works / what we keep" disclosure. AI-generated is stated on setup, live, and
  feedback.
- **a11y + mobile** — labelled controls, `aria-live` status, focus rings, responsive
  reflow, `prefers-reduced-motion` respected.
- **Tests** — Vitest component tests for the new structure (Settings delete flow,
  FeedbackReport get-then-generate, History actions, JobPreview collapse) and an
  `api.test.ts` that exercises the real fetch helper.
- **"On Air" visual redesign** — a pine/amber identity with the voice waveform as the
  through-line: an animated waveform on the live screen, VU-meter gauges for scores,
  per-interview waveform thumbnails + score rings in history. Canvas "instruments" live
  in one shared `instruments.tsx`.

Deliberately **not** built: React Query (server-state cache/retry) and OpenAPI codegen —
both slotted for Phase 6/7 when there's real traffic and a larger API surface.

## Challenges faced (and how they were solved)

### 1. Routing over non-serializable session state
The live `Room` (a WebRTC connection) and the assembled job/résumé must survive the
setup → interview → feedback route changes, but none of it can live in a URL. Solved with
an `InterviewProvider` context that instantiates `useInterviewRoom` once and holds the
wizard state; routes that can stand alone (`/feedback/:id`, `/history`, `/settings`) load
by id on mount, and `/interview` guards against a refresh by redirecting home.

### 2. An audio-playback regression born from cleverness
`useInterviewRoom` first attached the agent's audio to an **in-memory** `<audio>` element
that was never added to the page — and detached media elements don't reliably play. The
user heard silence. The tell was a `POST /feedback/generate 400`: the backend's
groundedness guard (`require_groundable_transcript`) refuses to score a transcript with no
candidate speech — which traced straight back to "couldn't hear the agent, so didn't
answer." Fixed by appending the element to the DOM and calling `play()`. Lesson: don't be
clever with media elements; the boring DOM element is the working one.

### 3. `res.json is not a function` on the first real API click
The `api.ts` `json()` helper was typed to take a `Response`, but every caller handed it a
`Promise<Response>` from `authedFetch`. `res.ok` was `undefined` → it fell into the error
path → called `.json()` on a Promise. This affected *every* JSON endpoint, not just the one
clicked. Root-cause fix: `await` the argument once, in the helper. The component tests mock
`api` wholesale and never exercised the helper, so I added `api.test.ts` that mocks only
`authedFetch` — the regression now fails a test.

### 4. Design by iteration, not by first draft
The first port was *consistent* but not *beautiful*. Rather than guess, I mocked the
redesign in a standalone HTML artifact and iterated on real feedback: the glowing red
"ON AIR" sign was both scary and semantically wrong on the setup screen (you're not
recording yet) → a calm green "You're all set" badge; broadcast jargon ("on air", "takes",
"the tape") risked confusing a non-native / non-technical audience → plain words, with the
personality carried by the *visuals*; flat green buttons → tactile "console-key" buttons.
Only after the mock was approved did it get ported into the components.

### 5. The header wasn't a navbar
The first shell centered the brand, tagline, and actions in a stack — which reads as a hero,
not navigation, and left "Sign out" floating over the interview screen. Restructured into a
proper top bar (brand left, New/History + a profile menu right), with account actions tucked
under an avatar menu and the whole nav hidden during a live session. Login kept its own
centered hero.

## What I'd improve / deferred

- **No client cache** — `History` re-fetches on every visit (spinner flash). Correct and
  always-fresh, but React Query (Phase 6/7) or a small context cache would make it instant.
- **Live waveform is synthetic** — it animates, but isn't driven by the actual audio. An
  `AnalyserNode` on the agent's track would make it react to real speech.
- **Feedback isn't pinned to moments** — the mock showed strengths/weaknesses as markers on
  the session waveform, but the feedback model returns no per-moment timestamps, so pinning
  would fake precision. The honest next step is a backend change: have the model return a
  short transcript quote per point — which is also a groundedness win.
- **Job URL parsing removed from the UI** — scraping arbitrary postings is unreliable
  (paywalls / JS / auth), and a field that usually errors confuses users. The backend
  endpoint still exists if it's ever worth revisiting.
- **Theme** — dark mode works via `prefers-color-scheme`; there's no in-app toggle yet.
