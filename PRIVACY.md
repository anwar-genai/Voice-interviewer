# Privacy Policy — AI Interview Coach

*Last updated: 2026-07-13. This is the operating policy for the deployed app. If you
fork and publish this project, review it, verify the provider links, and put your
own contact address at the bottom before going live.*

AI Interview Coach is a practice tool: you rehearse a job interview with an AI
interviewer and get feedback on how you did. To do that, it has to process some
personal data. This document says exactly what, where it goes, how long it's kept,
and how to delete it.

## What we collect, and why

| Data | Why we need it | Where it lives |
|---|---|---|
| Account email | Sign-in (email + password via Supabase Auth) | Supabase Auth |
| Job description text | Personalizes the interview questions | Postgres (Supabase), snapshotted per interview |
| Résumé text | Personalizes questions; extracted from your PDF | Postgres, snapshotted per interview |
| Voice audio | The interview itself — transcribed live to drive the conversation | **Processed in real time, never stored** |
| Interview transcript | Your feedback is scored from it; you can re-read it | Postgres |
| Feedback scores & notes | The product's output, shown in your history | Postgres |
| Consent record | Timestamp of your consent to voice + résumé processing | Postgres, on the interview row |
| Operational telemetry | Latency/cost metrics and error reports to keep the service working | Logs/metrics, **PII-redacted first** (names, emails, phone numbers are stripped before anything is logged or traced) |

What we deliberately **don't** do:

- **No raw audio retention.** Speech is transcribed in flight; when the session
  ends the audio is gone. Only the text transcript is kept.
- **No ads, no selling data, no third-party analytics.**
- **No training on your data.** Your transcripts and résumés are used to run *your*
  interviews and nothing else.

## Consent

Every interview starts with an explicit consent checkbox covering voice recording
and résumé processing — the interview cannot start without it, and the consent
timestamp is stored with the interview. Withdrawing is self-serve: delete your data
(below) and stop using the app.

## Subprocessors

Running the service means passing data through these providers. Each one receives
only what its job requires:

| Provider | Role | Data it processes | Terms / DPA |
|---|---|---|---|
| Supabase | Auth + Postgres database | Email, job/résumé text, transcripts, feedback | supabase.com/legal |
| LiveKit Cloud | Real-time voice transport (WebRTC) | Live audio streams, room metadata (job/résumé snapshot) | livekit.io/legal |
| Deepgram | Speech-to-text and text-to-speech | Live audio (in), transcript text, agent speech (out) | deepgram.com/legal |
| Cerebras | LLM inference (interviewer + feedback) | Job/résumé text, transcript (name-redacted for scoring) | cerebras.ai — privacy policy |
| Fly.io | Backend hosting | Everything the API/worker touches, in transit | fly.io/legal |
| Vercel / Cloudflare Pages | Static frontend hosting | No user data beyond serving the page | vercel.com/legal |
| Sentry *(optional, off by default)* | Error reporting | Error events, PII-redacted before send | sentry.io/legal |

*Before operating this for real users, confirm each provider's current DPA at the
page above and keep a signed/accepted copy where your org stores contracts.*

## Retention & deletion

- **Automatic:** interviews (with their transcripts and feedback) are purged after
  **30 days** (`RETENTION_DAYS`, enforced by a scheduled job). Interviews stranded
  by a crash are marked closed within hours.
- **Self-serve:** *Settings → Delete everything* erases all of your interviews,
  transcripts, résumé snapshots, and feedback immediately and permanently (the
  delete cascades at the database level). Your Supabase auth account can be removed
  on request.
- Backups, where the database host keeps them, expire on the host's standard cycle.

## Where data lives (residency)

The default deployment is US-centric: the database and backend run in the regions
chosen at setup (Supabase project region, Fly.io region), and Deepgram and Cerebras
process requests in the United States. LiveKit Cloud routes media through its
nearest edge.

If a deployment must keep data in one jurisdiction (e.g. EU-only): pin Supabase and
Fly.io to EU regions, self-host LiveKit in-region, and swap Cerebras for an
in-boundary LLM (AWS Bedrock / Azure OpenAI / Vertex in the target region) — the
LLM core is provider-agnostic behind one module (`backend/app/llm/`), and
`DEPLOYMENT.md` § residency covers the trade-offs. The current public deployment
makes no EU-residency claim.

## Voice is sensitive data

Voice can be biometric data under some laws (e.g. Illinois BIPA) and GDPR treats it
carefully. Our posture: explicit per-interview consent, no raw-audio storage, no
voiceprints, no identification — audio is used only to transcribe what you said,
then discarded.

## Your rights

View your data (History screen), delete it (Settings screen), or ask us anything
about it — GDPR-style access/erasure requests included — at the address below.

**Contact:** open an issue on the repository, or email the operator —
aannookhan@gmail.com.
