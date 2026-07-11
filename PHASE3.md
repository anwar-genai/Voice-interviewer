# Phase 3 — Complete the Product Loop

What shipped, what was genuinely hard, and what I'd improve. Companion to
`ROADMAP.md` Phase 3; written as a retro so the challenges are presentable
per phase.

## What shipped

A candidate can now finish an interview and get a **saved, grounded, actionable
score** — the roadmap's "done when" for this phase:

- **Transcript capture** — the agent worker persists every spoken turn and
  drives interview lifecycle status (`created → in_progress → completed/dropped`).
- **Feedback wired end-to-end** — End Interview → the server scores the *saved*
  transcript once, stores it, and re-serves it forever (idempotent; no re-billing).
- **Feedback report + history UI** — scores, strengths/improvements/
  recommendations, full transcript, the JD snapshot, past interviews with
  scores, and retake-from-snapshot.
- **Output-side safety** — a groundedness guard that refuses to score interviews
  with too little candidate speech, plus prompt hardening for output safety
  (no bias/defamation) and on-task moderation of the live agent.
- **Feedback evals** — a deterministic groundedness check and a calibration
  check (same transcript scored 3×, spread must stay tight).

## Challenges faced (and how they were solved)

### 1. Getting a transcript out of a live voice pipeline
The voice session runs in a **separate process** (the LiveKit agent worker),
not in the API. There is no request/response moment where a transcript
"arrives" — turns happen in real time inside the worker. Solution: the worker
shares the database and subscribes to the session's `conversation_item_added`
event, writing each turn as it happens. The capture module duck-types the
events so the persistence layer needs no LiveKit dependency.

### 2. Persistence must never hurt the live call
First version wrote to Postgres synchronously *on the voice event loop* — a
slow database would have frozen turn-taking for every session on the worker.
Fixed: all writes go through **one dedicated writer thread**, which also
serializes them (turn order preserved for free). Timestamps are captured at
event time, not write time, so ordering survives retries.

### 3. A DB outage must not silently eat the interview
Capture is deliberately best-effort (a DB hiccup must never crash a live
interview), but "log and drop" meant a 20-minute interview could vanish —
unrecoverable, since we don't retain audio by design. Fixed: failed turn
writes are **buffered in memory and re-flushed** with the next write or at
session close.

### 4. Scoring had to be trustworthy before it was pretty
Two failure modes matter for an interview coach: hallucinated praise and
double-billing. Addressed with (a) a **groundedness guard** — if the candidate
said fewer than ~20 words, refuse to score instead of letting the model invent
strengths; (b) **idempotent scoring** — feedback is generated once per
interview and re-read after that; (c) a **race fix** — two simultaneous
"End Interview" clicks used to mean two LLM bills and a 500 on the unique
constraint; the loser now returns the winner's row.

### 5. The real world is noisy
A literal fan in the room made the agent stop mid-sentence: background noise
tripped voice-activity detection, which read as the user barging in. Fixed
with tunable knobs (`VAD_ACTIVATION_THRESHOLD`, `MIN_INTERRUPTION_DURATION_SECONDS`)
plus LiveKit's built-in false-interruption auto-resume. Lesson: voice apps need
*calibration knobs*, not just correct code — the physical world doesn't match
the model.

### 6. Lifecycle truth needs a janitor
If the worker crashes, the session close event never fires and the interview is
stranded as `in_progress` forever. The retention job now doubles as a sweeper:
anything `in_progress` for 6+ hours is marked `dropped`.

### 7. Measuring feedback quality without fooling ourselves
Full groundedness evaluation needs a strong judge model (Phase 4). What's
honest *now*: a deterministic check that the guard rejects thin transcripts,
and a calibration check that the same transcript scored three times lands
within a tight spread. A small floor beats an impressive-looking eval that
proves nothing.

## Deliberate shortcuts (with upgrade paths)

| Shortcut | Ceiling | Upgrade when |
|---|---|---|
| One writer thread for all transcript writes | Serializes across sessions | Queue per session if a worker hosts many concurrent interviews |
| Turn buffer lives in memory | Lost if the worker process dies mid-outage | Local spill file, if that ever actually happens |
| Groundedness = word count | Doesn't verify quoted evidence exists in the transcript | Citation check / LLM judge (Phase 4) |
| Race fix returns winner's row | Loser still paid for one extra LLM call in the window | Row lock — not worth holding a DB transaction across an LLM call at single-worker scale |
| History score via lazy-load (N+1) | Fine for one user's own history | `selectinload` if users have thousands of interviews |
| Lifecycle events are log lines | Not queryable dashboards | Structured events/metrics sink (Phase 4) |

## What to improve next (feeds Phase 4/5)

- **Citation-level groundedness**: verify that quotes in the feedback actually
  appear in the transcript — the cheapest real hallucination defense.
- **Interrupted turns**: the transcript stores the agent's full generated text
  even when the user cut it off mid-sentence, so it can contain questions never
  actually spoken. `ChatMessage.interrupted` exists; use it.
- **Retake linkage**: attempts at the same job aren't formally linked
  (`retake_of`), which blocks per-job progress trends.
- **App.tsx decomposition**: four screens in one ~700-line component —
  scheduled Phase 5 work.
- **Calibration depth**: more transcripts, more runs, and a different judge
  model — scheduled Phase 4 work.
