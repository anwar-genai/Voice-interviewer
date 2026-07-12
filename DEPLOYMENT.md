# AI Interview Coach — Deployment Guide

How to take this app to production, across self-hosted / AWS / Azure / GCP, plus a
recommended target for the project's current stage. See `ROADMAP.md` for the broader
production plan; this doc is deployment-specific.

---

## What you're actually deploying (read this first)

This is **not one service** — it's four moving parts with very different needs, and
one of them breaks the usual serverless playbook.

| Component | Archetype | Deployment reality |
|---|---|---|
| **Frontend** (React/Vite) | Static assets | Trivial — any CDN/static host. |
| **Backend API** (FastAPI) | Stateless HTTP | Easy — containers or serverless. |
| **Agent worker** (`run_agent.py`) | **Long-running, stateful process** | The hard part. Holds a persistent WebSocket + live audio sessions. **Cannot be serverless** (no Lambda / Cloud Functions). Needs persistent compute, session-based autoscaling, graceful drain, and it loads the Silero VAD model in memory. |
| **LiveKit SFU** | Real-time media server | Managed (LiveKit Cloud) *or* self-host (open source). The central decision. |
| + Postgres, Redis, external APIs (Cerebras, Deepgram) | | From roadmap phases 1–2. |

### The GPU fork — decide this before anything else
- **Keep API providers** (Cerebras LLM, Deepgram STT/TTS) → everything runs on cheap
  **CPU containers**, no GPUs. *Recommended until scale or privacy forces otherwise.*
- **Self-host the models** (Whisper, Piper/XTTS, vLLM) → you now need **GPUs**, a
  5–10× cost and ops jump.

### The LiveKit decision — drives everything else
Keep **LiveKit Cloud** unless a compliance/residency requirement forces self-hosting.
The SFU is the single hardest thing to operate (WebRTC: TURN servers, UDP port ranges,
Redis for multi-node, TLS, media scaling). Self-hosting it adds a pager without making
the product better.

---

## ⭐ Recommended target architecture (this project's stage)

For a small team that wants production-grade without a platform team. Skip the
hyperscalers for now:

| Component | Service | Why |
|---|---|---|
| Frontend | **Vercel** or **Cloudflare Pages** | Zero-config static + edge CDN. |
| Backend API | **Fly.io** or **Render** | Simple container deploy. |
| **Agent worker** | **Fly.io Machines** (or Render Background Worker) | Both run *persistent processes* well; Fly's persistent Machines + good UDP/WebRTC support fit the worker. |
| LiveKit SFU | **LiveKit Cloud** | Don't self-host the SFU yet. |
| DB + Auth + Storage | **Supabase** | Postgres + Auth + file storage in one — collapses roadmap phases 1–2. |
| Redis (rate-limit) | **Upstash** or Fly Redis | Managed, cheap. |
| LLM / STT / TTS | **Cerebras + Deepgram** (keep) | No infra to run. |
| Secrets | Platform secret stores | Not `.env`. Rotate the current local keys first. |
| Observability | **Sentry** + **Langfuse/Helicone** + LiveKit metrics | See `ROADMAP.md` Phase 4. |

Roughly a day of setup, no Kubernetes. Graduate to a hyperscaler when you need
in-boundary LLMs for PII, existing-cloud commitments, or large scale.

---

## Runbook (Phase 6 — the recommended path, concretely)

The repo ships deploy-ready: `backend/Dockerfile` (one image for API + worker),
`backend/fly.toml` (two process groups, health checks, metrics), and a CI deploy
job that runs on every push to `main` once the secret exists.

### One-time setup

```bash
# 1. Fly app (from backend/ so it picks up fly.toml)
cd backend
fly launch --no-deploy          # accept the existing fly.toml; rename app if taken

# 2. Secrets — this is also the key-rotation moment Phase 1 flagged:
#    generate FRESH keys in each provider's dashboard (the local .env ones are
#    considered exposed), and set them only here. Never `fly deploy` from a
#    machine where .env could leak into the context (.dockerignore blocks it).
fly secrets set \
  LIVEKIT_URL=wss://<project>.livekit.cloud \
  LIVEKIT_API_KEY=... LIVEKIT_API_SECRET=... \
  CEREBRAS_API_KEY=... DEEPGRAM_API_KEY=... \
  SUPABASE_URL=https://<project>.supabase.co \
  DATABASE_URL='postgresql+psycopg://...pooler.supabase.com:5432/postgres' \
  CORS_ORIGINS=https://<your-frontend-domain> \
  SENTRY_DSN=...                # optional but do it — errors page no one without it

# 3. First deploy (migrations run automatically as the release command)
fly deploy

# 4. Frontend: import the repo into Vercel or Cloudflare Pages,
#    root directory = frontend/, build = npm run build, output = dist/.
#    Env vars: VITE_API_BASE=https://<fly-app>.fly.dev
#              VITE_SUPABASE_URL + VITE_SUPABASE_PUBLISHABLE_KEY
#    Then make sure CORS_ORIGINS (step 2) matches the domain it gives you.

# 5. Push-to-deploy: add FLY_API_TOKEN to GitHub repo secrets
fly tokens create deploy        # -> Settings -> Secrets -> Actions -> FLY_API_TOKEN

# 6. Retention purge (cron target) — a scheduled machine on the same image:
fly machine run . --schedule daily "python -m app.db.retention"
```

### What you get

- **Health checks:** API `GET /health`; worker `GET :8081/` (built into
  `livekit-agents` start mode). Fly restarts what fails them.
- **Graceful drain:** deploys send SIGTERM and wait `kill_timeout` (5m, Fly's
  max) so live interviews can finish; the worker stops accepting new rooms
  immediately. Interviews longer than 5m at deploy time get cut — deploy idle.
- **Dashboards:** worker Prometheus metrics on :9464 are scraped by Fly →
  https://fly-metrics.net (managed Grafana), plus `fly logs` for both processes.
- **TLS/edge:** automatic on Fly and the static host; CORS stays enforced
  in-app from `CORS_ORIGINS`.
- **Dependency scanning:** Dependabot PRs weekly (pip, npm, GitHub Actions);
  CI + the evals gate decide if an update is safe.

### Scaling ceilings (deliberate, documented)

- One `api` machine — rate limiting is in-process (`app/core/ratelimit.py`);
  move it to Upstash Redis before `fly scale count api=2+`.
- One `worker` machine ≈ a handful of concurrent interviews (it reports
  load and LiveKit stops dispatching at 0.7); `fly scale count worker=N`
  when sessions actually collide.

---

## Component × platform matrix

| Need | Self-host / OSS | AWS | Azure | GCP |
|---|---|---|---|---|
| **Frontend** | Nginx / Caddy | S3 + CloudFront | Static Web Apps / Blob + Front Door | Cloud Storage + Cloud CDN / Firebase |
| **Backend API** | Docker Compose / K8s | ECS Fargate / App Runner | Container Apps / App Service | Cloud Run |
| **Agent worker** ⚠️ | K8s Deployment (not a Job) | ECS/EKS **persistent** service | **Container Apps** (long-running, KEDA) | **GKE** (Cloud Run is a weaker fit) |
| **LiveKit SFU** | Self-host (TURN + Redis + UDP) | LiveKit Cloud *or* EC2/EKS behind NLB (UDP) | LiveKit Cloud *or* AKS/VMs | LiveKit Cloud *or* GKE/GCE |
| **Postgres** | Postgres container | RDS / Aurora | Azure DB for PostgreSQL | Cloud SQL / AlloyDB |
| **Redis** | Redis container | ElastiCache | Azure Cache for Redis | Memorystore |
| **Secrets** | Vault / SOPS | Secrets Manager / SSM | Key Vault | Secret Manager |
| **Registry** | Harbor / GHCR | ECR | ACR | Artifact Registry |
| **LLM (in-boundary)** | vLLM / Ollama (GPU) | **Bedrock** (Claude, Llama) | **Azure OpenAI / AI Foundry** | **Vertex AI** (Gemini, Model Garden) |
| **STT/TTS (native)** | Whisper / Piper / XTTS | Transcribe / Polly | Azure Speech | Speech-to-Text / Text-to-Speech |
| **Observability** | Grafana + Prometheus + Loki + Tempo | CloudWatch + Managed Grafana + ADOT | Azure Monitor + App Insights | Cloud Operations Suite |

---

## Per-cloud notes

### AWS
Most mature, most levers. Worker on **ECS Fargate** (EKS at scale). Native win:
**Bedrock** serves Claude *and* Llama inside your VPC, so resumes/voice never leave
your boundary — directly relevant to the PII situation. Gotcha: self-hosting LiveKit
needs a **Network Load Balancer** (UDP) or host networking — WebRTC doesn't work
behind a standard ALB.

### Azure
Standout is **Container Apps**: native support for long-running background processes
with **KEDA** event-driven autoscaling — the best managed fit for the agent worker.
Native LLM is **Azure OpenAI**; voice via **Azure Speech**. Best if you're a
Microsoft shop or want Azure OpenAI.

### GCP
**Cloud Run** is the nicest experience for the *stateless API* (WebSockets, scale to
zero), but put the *persistent worker* on **GKE Autopilot** — Cloud Run's
request-scoped model fights the always-connected worker. Native LLM is
**Vertex AI / Gemini** (Gemini Flash is also a strong live-interviewer candidate,
and here it's in-boundary).

---

## Fully open-source / self-hosted path

For zero external dependencies (privacy, on-prem, cost at scale):
- **Media:** self-host LiveKit (SFU + TURN + Redis) on Kubernetes.
- **Models on GPUs:** **vLLM** or **TGI/SGLang** (LLM), **faster-whisper** (STT),
  **Piper/Kokoro/XTTS** (TTS). Ollama for dev only.
- **Data:** Postgres + Redis containers; MinIO for resume storage.
- **Orchestration:** Docker Compose (single box) → **Kubernetes** (scale worker and
  SFU independently).
- **Where:** cheap GPU hosts (Hetzner), burstable GPU (Runpod/Modal), or own hardware.
- **Reality check:** a real ops project — WebRTC + GPU serving + model tuning at once.
  Worth it for privacy/scale mandates; overkill while still finding users.

---

## Cross-cutting concerns (every platform)

- **Worker autoscaling** — scale on **concurrent sessions**, not CPU. Use LiveKit's
  `drain_timeout` / graceful shutdown so deploys never kill a live interview. Set
  `num_idle_processes` for warm capacity.
- **WebRTC networking** (self-hosted LiveKit only) — UDP port ranges, a TURN server
  for restrictive networks, TLS. The #1 self-host pain point.
- **PII / data residency** — you store **resumes + voice**. Strongest argument for a
  hyperscaler with an **in-boundary LLM** (Bedrock / Azure OpenAI / Vertex) over
  shipping data to external APIs; may dictate your region. Feeds Phase 7 compliance.
- **Cost attribution** — four metered surfaces (LiveKit minutes + LLM tokens + STT +
  TTS audio). Tag per interview (ties to the Phase 4 o11y plan).

---

## How to choose

1. **Just want to ship?** → the ⭐ recommended path (Fly.io/Render + LiveKit Cloud +
   Supabase). Stop there.
2. **Committed to a hyperscaler / need in-boundary LLM for PII?** → match your existing
   cloud; use its native LLM (Bedrock / Azure OpenAI / Vertex).
3. **Hard privacy/on-prem or huge scale?** → full self-host on Kubernetes with GPUs.
   Budget for ops.
4. **Always:** keep LiveKit Cloud until a requirement forces otherwise; keep the worker
   on persistent compute, never serverless.
