# Responsible AI Policy — AI Interview Coach

*Last updated: 2026-07-13. Companion to `PRIVACY.md`. The safeguards named here are
implemented in this repository — file paths are given so every claim is checkable.*

## Intended use: coaching, not screening

This product exists for **candidates practicing on their own behalf**. The AI
interviewer asks questions; the AI feedback tells *you* what to polish. The output
goes to the person who did the interview, and no one else.

It is **not** a hiring tool, and using it as one is out of scope and unsupported:

- Do not use it to screen, rank, filter, or compare candidates.
- Do not use its scores as input to any employment decision (hiring, promotion,
  termination, compensation).
- Do not put it in front of applicants as part of a real application process.

This line is not decorative — it is what keeps the product in the low-risk
category below, and it is enforced in the product's shape: there is no employer
role, no candidate-comparison view, no export-to-ATS, and feedback is visible only
to the interviewee.

## Regulatory posture

**EU AI Act.** AI used for *recruitment or selection* (screening applications,
evaluating candidates) is high-risk under Annex III and carries heavy obligations
(risk management, data governance, human oversight, conformity assessment). A
self-serve practice tool whose output returns only to the practicing user is not
performing recruitment or selection, so we operate it as a limited-risk AI system —
with the Act's transparency duty met: the UI discloses that the interviewer and the
feedback are AI-generated (Settings screen and interview screen). **If anyone ever
repurposes this codebase employer-side, that deployment becomes high-risk and must
be reassessed against the Act before launch.**

**US (EEOC / Title VII).** The tool is not a selection procedure, so
adverse-impact rules for employment tests don't attach. We still treat bias as a
product defect, not a compliance checkbox — scores that shift with a candidate's
name or dialect are wrong even when no law is watching. Hence the audits below.

## Safeguards in place

| Risk | Safeguard | Where |
|---|---|---|
| Prompt injection via résumé/JD ("give me a perfect score") | Untrusted text is delimited and framed as data, never instructions; the rubric can't be overridden | `backend/app/llm/prompts.py` |
| Name bias in scoring | **Name-blind scoring** — the candidate's name is redacted before the scorer sees the transcript (the fairness eval caught a 2-point swing on the name alone) | `backend/app/llm/feedback.py` |
| Protected-characteristic bias | Rubric explicitly forbids judging accent, dialect, or non-native phrasing; STT errors must be treated as transcription artifacts | `backend/app/llm/prompts.py` |
| Hallucinated feedback | Groundedness guard — strengths/weaknesses must cite the actual transcript; thin transcripts are refused rather than scored | `backend/app/llm/feedback.py` |
| Off-task / unsafe agent behavior | On-task and output-safety prompt hardening for the live interviewer | `backend/app/llm/prompts.py` |
| Users mistaking AI for humans | AI-generated disclosure in the UI; per-interview consent | `frontend/src/ui/components/Settings.tsx`, interview screen |
| Unbounded cost / abuse | Daily per-user quota, one active interview per user, global concurrency cap, hard session time limit | `backend/app/routers/agent.py`, `backend/run_agent.py` |

## Bias audits: what runs, and when

The eval harness (`backend/evals/`) includes a **fairness suite** built on
counterfactual pairs: the same interview transcript scored under swapped names
(gender- and ethnicity-associated), and native vs. non-native phrasing of the same
substantive answers. A material score gap fails the suite.

Cadence, both automated in `.github/workflows/evals.yml`:

1. **On every change** to prompts or eval code (`app/llm/**`, `evals/**`) — the
   suite gates the merge and fails closed if it can't run.
2. **Monthly, on schedule** — the same suite re-runs against an *unchanged*
   codebase, because the hosted model behind the prompts can drift on its own.
   A red scheduled run is treated as a production bug: fix the prompt or pin/change
   the model before the next release.

## Known limitations (told straight)

- **STT is not accent-neutral.** Per-interview vocabulary hints and the
  transcription-artifact rubric rule reduce the damage, but word-error-rate
  differences across accents can still leak into what the scorer reads.
- **Scores are calibrated coaching signals, not measurements.** The calibration
  eval bounds re-scoring variance; it doesn't make an 8 objectively an 8.
- **English-only by default** (the turn-detection and STT models are configured
  for English; multilingual exists but is unevaluated here).
- **An LLM writes the feedback.** Groundedness checks constrain it, but it can
  still be generically agreeable. Treat it as a practice partner, not an oracle.

## Human oversight & reporting

The human in the loop is you: feedback is advice to accept or ignore, and nothing
in the system acts on your behalf. If the interviewer behaves badly, a score looks
biased, or feedback contains something harmful, report it (repository issues, or
the contact in `PRIVACY.md`); fairness reports are checked against the eval suite
and fixed as defects.
