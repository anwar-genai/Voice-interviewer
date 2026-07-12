# Phase 7 — Scale, cost & compliance

What shipped, what was genuinely hard, and what I'd improve. Companion to
`ROADMAP.md` Phase 7.

## What shipped

The roadmap's bar: usage is bounded by cost, and the legal/responsible-AI
posture is documented and defensible.

- **Cost controls at the front door** — `/agent/join-token` now runs three
  DB-backed checks before any room or LLM money moves: a **daily per-user
  quota** (`DAILY_INTERVIEW_LIMIT`, 10/day → 429), **one active interview per
  user** (409), and a **global concurrency cap** (`MAX_CONCURRENT_INTERVIEWS`,
  10 → 503). All three are COUNT queries on the existing `interviews` table —
  no new tables, no Redis — so unlike the in-process rate limiter they survive
  restarts and hold across machines. "Active" rows age out of a time window,
  so a crashed worker or a never-joined room can't lock a user out forever.
- **Hard cap on interview length** — the agent worker arms a timer at session
  start (`MAX_INTERVIEW_MINUTES`, 30). When it fires, the agent says a natural
  goodbye, then deletes the room server-side, which disconnects the candidate
  and closes the session (the existing close handler marks the interview
  completed). Server-side because the client can't be trusted to hang up on
  itself. The frontend now shows "Interview ended" + "Get my feedback" instead
  of a red "Disconnected" badge.
- **Extraction cache** — re-practicing the same job is the product's core
  loop, and every repeat parse of an identical JD was a paid LLM call. A tiny
  in-process hash→result cache (successes only) makes the second parse free.
- **`PRIVACY.md`** — the actual operating policy: what's collected and why,
  what's deliberately not (raw audio, training, ads), the **subprocessor
  table** (Supabase/LiveKit/Deepgram/Cerebras/Fly/Vercel/Sentry — what each
  one sees, where its DPA lives), retention/deletion mechanics, and the
  **data-residency posture** (US-centric by default; the documented EU-only
  path is region-pinned Supabase/Fly + self-hosted LiveKit + an in-boundary
  LLM per `DEPLOYMENT.md`).
- **`RESPONSIBLE_AI.md`** — intended use ("coaching, not screening") stated as
  a hard product boundary, the **EU AI Act / EEOC analysis** of why that
  boundary keeps this out of the high-risk employment category (and the
  explicit warning that an employer-side fork flips it), a safeguards table
  that maps every claim to a file in this repo, known limitations told
  straight (STT accent sensitivity, score calibration limits), and the bias-
  audit cadence.
- **Bias audits became a schedule, not a promise** — `evals.yml` gains a
  monthly cron. The fairness counterfactuals (name swaps, non-native phrasing)
  already gated prompt *changes*; the scheduled run re-checks an *unchanged*
  codebase, because the hosted model behind the prompts can drift on its own.
- **UI links the policies** — the Settings screen (already the transparency +
  data-deletion surface) now links both documents and states the 30-day
  retention.
- **7 new tests** (`tests/test_phase7_cost.py`) — quota trips at the limit,
  yesterday's interviews don't count, second concurrent interview rejected,
  global capacity 503, stale rows age out, repeat JD parse isn't re-billed,
  failures never poison the cache.

Deliberately **not** built:

| Skipped | Why / upgrade when |
|---|---|
| Teams / multi-tenancy | No team concept exists anywhere in the product — a solo candidate practices alone. Building org structures for zero orgs is the definition of speculative. Revisit only if a second stakeholder (coach, bootcamp) ever appears. |
| Redis for quotas/cache | The quota checks are DB-backed (already multi-machine-safe); the extraction cache and rate limiter are in-process on the one API machine `fly.toml` pins. Redis lands as one change when `fly scale count api=2` happens, same as the Phase 6 note. |
| Billing / paid tiers | Quotas bound cost; nothing charges money. Stripe is a product decision, not an infra gap. |
| A lawyer | `PRIVACY.md`/`RESPONSIBLE_AI.md` are engineering-honest and map to real code, which is more than most prototypes have — but they're not legal advice, and the docs say so. Real launch → real review. |
| Per-user spend dashboards | The per-interview usage/cost summaries exist since Phase 0 and land in Grafana since Phase 6; a per-user rollup is a dashboard query away when someone actually asks. |

## Challenges faced (and how they were solved)

### 1. The tests that quietly called production LiveKit
The first version of two tests asserted "this request passes the cost gates" by
checking the response wasn't 409/429/503 — and in an environment with a real
`backend/.env`, passing the gates meant the API **actually created LiveKit
rooms**. The standalone run's log gave it away: `200 OK` where CI would see
500, and three-second call latencies. Worse than the stray rooms themselves: a
developer running `run_agent.py dev` alongside pytest would have had the agent
auto-dispatch into a test room and start billing Deepgram/Cerebras for talking
to nobody. Fix: those tests blank `livekit_url` via monkeypatch, making "past
the gates" a deterministic config-500 in every environment. Lesson: *"the test
passed" and "the test did what you think" are different claims — read the log
once.*

### 2. Where does "active" end? (stranded rows vs. hard locks)
"One interview at a time" sounds like a boolean until you ask what happens
when a worker crashes mid-session or a user pays for a room and never joins:
the row strands at `in_progress`/`created`, and a naive check locks that user
out **forever**. The retention job already sweeps stale rows, but a cost gate
can't depend on a cron having run recently. Fix: "active" means *recently
touched* — status in (created, in_progress) **and** updated inside the
session-length window (+ slack). Stranded rows age out of the gate on their
own; the cron still tidies the data later. Two failure systems, neither
load-bearing for the other.

### 3. Ending an interview that the client won't end
The duration cap has to hold against a closed laptop, a dead tab, or a client
that simply ignores timers — so it can't live in the frontend. The worker owns
the clock: `asyncio.sleep(max)` → the agent speaks a wrap-up (awaiting the
`SpeechHandle` so the goodbye finishes playing) → `ctx.delete_room()`, which
force-disconnects everyone and triggers the normal close path (transcript
flushed, status → completed). The subtlety was the *other* ending: if the user
leaves first, the timer task must not blow up a dead session — it swallows the
failure and logs at debug, and the job process dying with the room reaps it
anyway.

### 4. Writing compliance docs that aren't cosplay
The easy failure mode for "add a privacy policy" is downloading boilerplate
that claims things the code doesn't do. These docs went the other way: every
sentence was checked against the repo, and two claims died that way — the
policy draft said "magic link" (the login is email+password) and nearly
overclaimed the PII redaction scope until `redaction.py` confirmed emails,
phones, and names are actually stripped. The safeguards table in
`RESPONSIBLE_AI.md` cites file paths precisely so the next person can keep the
docs honest the same way.

## Interview-ready: how to talk about this phase

**The one-liner:** "I bounded spend with three DB-backed gates and a
server-side session clock, then wrote the privacy and responsible-AI posture
as documents that cite the code that enforces them."

**Why quotas live in the database and not in memory:** the rate limiter (20
req/min) is in-process — fine, because a restart forgiving a one-minute window
is harmless. A *daily* quota that forgets on every deploy isn't a quota. The
interviews table already records who started what and when, so the quota is
just a COUNT over data that already exists — durable, multi-machine-correct,
zero new infrastructure. Rule of thumb: **limits whose window outlives a
process must outlive the process.**

**The vocabulary, in plain words:**
- **Subprocessor** — a company your users' data flows through so you can
  provide the service (here: Deepgram hears the audio, Cerebras reads the
  transcript). Users consent to *you*, so you owe them the list of who else
  is involved.
- **DPA (Data Processing Agreement)** — the contract with each subprocessor
  saying they only process the data on your instructions, protect it, and
  delete it. GDPR requires one with every processor.
- **Data residency** — *which country the data physically sits in.* Matters
  because some customers/laws require "EU data stays in the EU"; the answer
  here is documented honestly: US by default, with a named upgrade path
  (in-boundary LLM) rather than a pretend checkbox.
- **EU AI Act posture** — the Act treats AI that *selects candidates* as
  high-risk (heavy obligations). This product's output goes only to the
  person practicing, which is what keeps it limited-risk — and that's why
  "coaching, not screening" is enforced product shape, not a disclaimer.
- **Model drift** — the hosted LLM behind your prompts changes under you.
  Your prompts didn't change, your behavior did. That's why the bias audit
  runs monthly on a *schedule*, not only on code changes.

**The bulkhead framing (for "how do you control AI costs?"):** three nested
bounds — per-request (rate limit, Phase 1), per-user-per-day (quota), and
whole-system (concurrency cap + session clock). Any one failing still leaves
the outer bound holding; the worst possible bill is `concurrency cap ×
session length × per-minute provider cost`, a number you can compute before
it happens.

## What to improve next

- **Actually deploy** — still the runbook in `DEPLOYMENT.md`; unchanged from
  Phase 6, and now the policies the Settings screen links to are real files
  on `main`.
- **Redis (Upstash) for limiter + cache** — the moment `api` scales past one
  machine; the quota gates already don't care.
- **Per-user spend rollup** — join the worker's usage summaries to `user_id`
  in Grafana; turns "quota = 10/day" into "quota = $X/month" if costs ever
  need user-level accounting.
- **Sign the DPAs** — the table names where each provider's terms live; an
  actual operator should accept/countersign them and file copies (runbook
  material, like the Fly/Vercel account steps).
