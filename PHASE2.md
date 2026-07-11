# Phase 2 — Persistence & Data Lifecycle

What shipped, what was genuinely hard, and what I'd improve. Companion to
`ROADMAP.md` Phase 2. (Reconstructed retro — written after the phase landed.)

## Interlude first: the agent felt slow, and it wasn't the LLM

Between Phase 1 and Phase 2, real use showed the agent waiting up to **6
seconds of silence** before replying. The LLM was fast; the pipeline was
running VAD-only endpointing — "reply when the user has been quiet long
enough" — even though a semantic turn-detector model was already installed,
just never wired in. Fix: plug the end-of-utterance model into
`AgentSession` (it predicts *"has this person finished a thought?"* from the
words, not the silence), expose min/max endpointing delays as config, lower
the max to 4s. Lesson: in voice UX, *perceived* latency lives in turn-taking,
not token speed — and an unwired model is indistinguishable from a missing
one.

## What shipped

The roadmap's bar: interviews survive restarts, belong to a user, and can be
fully deleted on request.

- **Schema as code** — SQLAlchemy 2.0 models (`Interview`, `Turn`, `Feedback`)
  on Supabase Postgres, Alembic migrations.
- **Interviews persisted** — job/resume snapshot, room, status, and the
  consent timestamp saved on `/agent/join-token`.
- **Owner-scoped `/interviews` router** — list, get, stats, per-item and full
  erasure (GDPR); replaced the in-memory analytics dict.
- **Retention TTL** — `python -m app.db.retention` purges interviews past
  `RETENTION_DAYS` (cron target in Phase 6).
- **Persistence suite** — ownership scoping, cascade erasure, retention, on
  in-memory SQLite.

## Challenges faced (and how they were solved)

### 1. Three ways to connect to Supabase Postgres; two of them fail
The genuinely painful one. Supabase offers a direct connection and two
poolers, and the failure modes are silent-ish:
- **Direct connection** — IPv6-only; unreachable from most home networks.
  Hangs, then times out.
- **Transaction pooler (port 6543)** — connects fine, then **breaks Alembic**:
  DDL and prepared statements don't survive transaction-mode pooling.
- **Session pooler (port 5432)** — the one that actually works for this stack.

Add two more traps: the scheme must be `postgresql+psycopg://` (psycopg3, not
psycopg2), and a DB password containing `@ % :` corrupts the connection URL
because those characters are URL-reserved. Keeping the password alphanumeric
cost nothing; debugging the alternative cost an evening. All of it is now a
CLAUDE.md gotcha so it's paid for exactly once.

### 2. Resisting the users table
Every persistence tutorial starts with a `User` model. But Supabase already
*owns* the user store — duplicating it means sync bugs and a second source of
truth. Decision: the owner column is simply the Supabase JWT `sub` (a UUID
string). No users table, no foreign key to nowhere, no sync job. The schema
has exactly three tables.

### 3. Erasure that actually erases
GDPR deletion can't leave orphaned turns or feedback. Cascades are declared
**twice** on purpose: ORM-level (`cascade="all, delete-orphan"`) so app-path
deletes are complete, and DB-level (`ondelete="CASCADE"`) so nothing depends
on the app remembering. One `DELETE` on the interview removes everything.
Ownership checks return **404, not 403**, so a probing user can't learn that
someone else's interview id exists.

### 4. A database dependency that doesn't take the API hostage
Requiring `DATABASE_URL` at import time would break `/health` and every
DB-free code path. The engine is built lazily on first use — same pattern as
Phase 0's `require_*` config accessors. The API boots with no database;
anything that touches the DB fails clearly at the call site.

### 5. Schema now, data later — on purpose
`Turn` and `Feedback` tables were defined and migrated in this phase but only
*populated* in Phase 3. Designing the tables alongside `Interview` kept the
cascade/erasure story whole (delete once, everything goes), while keeping this
phase's scope to persistence rather than pipeline capture.

## Deliberate shortcuts (with upgrade paths)

| Shortcut | Ceiling | Upgrade when |
|---|---|---|
| Erasure via ORM loop + cascade | Loads rows to delete them | Bulk delete + DB cascade if volume grows |
| Retention is a manual/cron entry point | Nobody runs it automatically yet | Scheduler in Phase 6 |
| Status strings, no state machine | Nothing validates transitions | Only if states multiply |
| UUIDs as `String(36)`, JSON columns generic | Portable over optimal | Postgres-native types if perf ever asks |

## What to improve next (with hindsight)

- **Populate turns + feedback** → done in Phase 3 (agent-worker capture,
  wired feedback).
- **Stranded `in_progress` rows** — a crashed worker leaves zombie statuses;
  → fixed in Phase 3's hardening pass (retention job doubles as sweeper).
- **Consent is a timestamp, not a document** — fine until a lawyer asks which
  consent *text* was shown; version it in Phase 5's consent UI.
