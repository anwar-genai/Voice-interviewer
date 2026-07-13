# Deploy Checklist — from scratch to live (Render)

Tick boxes as you go (`[ ]` → `[x]`). Companion to `DEPLOYMENT.md` — this is
the same plan expanded into every click, targeting **Render** (chosen over
Fly.io because Render's free tier needs no card at all; Fly's Fly-specific
runbook stays intact in `DEPLOYMENT.md` § Runbook for client reference).
Delete this file (or keep it as a record) once you're live.

---

## Part 0 — Prerequisites (accounts)

You already have: Supabase, LiveKit Cloud, Cerebras, Deepgram, GitHub.
New accounts needed: Render, Vercel, Sentry (optional). No CLI installs
needed — Render deploys straight from the dashboard.

- [ ] Create a Render account at render.com (sign in with GitHub — makes repo import one click). **No card required** for the free tier
- [ ] Create a Vercel account at vercel.com (sign in with GitHub)
- [ ] (Optional but recommended) Create a Sentry account at sentry.io, free tier

---

## Part 1 — Rotate keys (the Phase 1 flag)

Your local `backend/.env` keys count as exposed — generate FRESH keys in each
dashboard now, and use only the fresh ones in Part 2. Don't put them in
`.env`; paste them straight into Render's dashboard (keep them in a scratch
notepad until Part 2 is done, then delete the notepad).

- [ ] **LiveKit** (cloud.livekit.io → your project → Settings → Keys): create a new API key/secret pair. Note all three: `LIVEKIT_URL` (wss://….livekit.cloud), key, secret. Delete the old key after the deploy works
- [ ] **Cerebras** (cloud.cerebras.ai → API Keys): create a new key, note it, revoke the old one after deploy
- [ ] **Deepgram** (console.deepgram.com → API Keys): same — new key now, delete old after deploy
- [ ] **Supabase DB password** (dashboard → Settings → Database → Reset database password): pick an **alphanumeric** password (symbols like `@ % :` corrupt the connection URL). This breaks your local `.env`'s `DATABASE_URL` too — update it there
- [ ] Build the new `DATABASE_URL` using the **session pooler** host (dashboard → Connect → Session pooler): `postgresql+psycopg://postgres.<ref>:<NEW-PASSWORD>@aws-0-<region>.pooler.supabase.com:5432/postgres`
- [ ] (Optional) **Sentry**: create a project (platform: Python), copy its DSN

---

## Part 2 — Create the two Render services

Both services build from the **same repo and the same `backend/Dockerfile`**
— only the start command differs. Create them one at a time.

### 2a. API — Web Service (Free plan)

- [ ] Render dashboard → **New → Web Service** → connect the `voice-interviewer` GitHub repo
- [ ] **Root Directory** = `backend`; **Environment** = Docker (it picks up `backend/Dockerfile` automatically)
- [ ] **Start Command**: leave blank if the Dockerfile has a CMD, otherwise `uvicorn uvicorn_app:app --host 0.0.0.0 --port 8000` — Render sets `$PORT` itself, so confirm this matches (Fly hardcodes 8000; Render may inject a different port env var — check the Dockerfile's `EXPOSE`/`CMD` against Render's port docs if the first deploy's health check fails)
- [ ] **Instance Type**: Free
- [ ] Don't deploy yet — add environment variables first (next step), then create the service

### 2b. Worker — Background Worker (Starter plan, $7/mo)

- [ ] Render dashboard → **New → Background Worker** → same repo
- [ ] **Root Directory** = `backend`; **Environment** = Docker; same Dockerfile
- [ ] **Start Command**: `python run_agent.py start`
- [ ] **Instance Type**: Starter (the free tier's 15-minute spin-down would kill live interviews — this is the one paid piece, ~$7/mo)

### 2c. Environment variables (set on BOTH services, identical values)

- [ ] On each service → **Environment** tab → add:

  ```
  LIVEKIT_URL=wss://<project>.livekit.cloud
  LIVEKIT_API_KEY=...
  LIVEKIT_API_SECRET=...
  CEREBRAS_API_KEY=...
  DEEPGRAM_API_KEY=...
  SUPABASE_URL=https://<project>.supabase.co
  DATABASE_URL=postgresql+psycopg://...pooler.supabase.com:5432/postgres
  CORS_ORIGINS=http://localhost:5173
  SENTRY_DSN=...
  ```

  (`CORS_ORIGINS` is a placeholder until Part 4 gives you the real frontend
  domain — update it on the **API service only** then. Skip `SENTRY_DSN` if
  you skipped Sentry. Render's env vars aren't shared across services by
  default — paste into both, or use a Render "Environment Group" to avoid
  duplication.)

---

## Part 3 — First deploy + migrations

- [ ] Trigger the first deploy (creating each service usually auto-triggers it) — watch the **Logs** tab on the API service for the image build
- [ ] **Shell / One-Off Jobs are paid-plan-only** (they show a lightning-bolt icon on Free) — instead, make migrations part of the container's own startup: API service → **Settings** → **Docker Command** (overrides the Dockerfile `CMD`) → set to:
  ```
  sh -c "python -m alembic upgrade head && uvicorn uvicorn_app:app --host 0.0.0.0 --port 8000"
  ```
  Save (triggers a redeploy). `alembic upgrade head` is a safe no-op once the schema's current, so leave this as the permanent start command — it runs on every future deploy too, same effect as Fly's `release_command`
- [ ] Watch **Logs** for the migration output, then uvicorn starting, with no errors
- [ ] Once the API service shows **Live**, open `https://<api-service>.onrender.com/health` → should return healthy JSON (first request may take ~30–60s if the free instance had spun down)
- [ ] Worker service → **Logs** tab — confirm it connected to LiveKit, no crash loop (first boot is slow: downloads the turn-detection model)

**If deploy fails:** check the **Logs** tab for the failing service —
migration failures are almost always `DATABASE_URL` (wrong host,
non-alphanumeric password, or `postgresql://` instead of
`postgresql+psycopg://`). Port mismatches show up as a failed health check
with the API otherwise looking "Live."

---

## Part 4 — Frontend on Vercel

> Vercel's free Hobby plan is **non-commercial use only**. Fine for a
> portfolio project; if this app ever charges users, move to Cloudflare Pages
> (free tier allows commercial use) — see `DEPLOYMENT.md` § "Free tiers,
> commercial-use terms & the Cloudflare Pages escape hatch" for the 7-step
> migration.

- [ ] vercel.com → Add New → Project → import the GitHub repo
- [ ] Set **Root Directory = `frontend`** (Vercel then auto-detects Vite; build `npm run build`, output `dist` — accept those)
- [ ] Add three environment variables before the first build:
  - `VITE_API_BASE` = `https://<api-service>.onrender.com`
  - `VITE_SUPABASE_URL` = `https://<project>.supabase.co`
  - `VITE_SUPABASE_PUBLISHABLE_KEY` = the **publishable** key (Supabase dashboard → Settings → API Keys — NOT secret/service_role)
- [ ] Deploy, note the domain Vercel gives you (`https://<something>.vercel.app`)
- [ ] Point CORS at it: Render dashboard → API service → Environment → update `CORS_ORIGINS=https://<something>.vercel.app` (triggers a redeploy — that's expected)
- [ ] Supabase dashboard → Authentication → URL Configuration: set **Site URL** to the Vercel domain and add it to **Redirect URLs** (otherwise email-confirmation links bounce to localhost)

---

## Part 5 — CI: push-to-deploy + evals gate

- [ ] Nothing to configure for deploy — Render auto-deploys both services on every push to `main` by default once the repo is connected (toggle under each service's **Settings → Auto-Deploy** if you ever want to turn it off)
- [ ] The repo's existing `ci.yml` still has a Fly-specific deploy job — harmless, it skips cleanly forever since `FLY_API_TOKEN` won't be set; no edit needed unless you want to delete that job later
- [ ] Add `CEREBRAS_API_KEY` as a GitHub Actions secret (repo → Settings → Secrets and variables → Actions) — the evals gate in `evals.yml` fails closed without it
- [ ] Verify: push any small commit to `main` → both Render services show a new deploy in their **Events** tab

---

## Part 6 — Retention cron

- [ ] Render dashboard → **New → Cron Job** → same repo, root `backend`, Docker environment
- [ ] Command: `python -m app.db.retention`; **Schedule**: `0 0 * * *` (daily at midnight UTC)
- [ ] Add the same `DATABASE_URL` env var (only that one's needed for this job)
- [ ] Cron Jobs bill per execution (seconds of compute), not a flat monthly fee — this should cost close to nothing given how fast the purge runs

---

## Part 7 — Verify end-to-end (the real test)

- [ ] Open the Vercel URL **on your phone**, sign up with a real email, confirm, log in
- [ ] Run a full mock interview: mic permission → paste a JD → talk to the agent → end → generate feedback → check it appears in History
- [ ] Render dashboard → both services' **Logs** tabs during the interview — turns being persisted, no `provider_error` events
- [ ] (If Sentry is set) sentry.io shows the project alive, zero errors — or real ones to fix
- [ ] Cleanup: delete the scratch notepad of keys from Part 1; delete/revoke the OLD provider keys in each dashboard if you haven't yet

**Done. The app is live.** Next polish steps are in the conversation / CLAUDE.md
"Next" — use it on a phone for a week before optimizing anything.
