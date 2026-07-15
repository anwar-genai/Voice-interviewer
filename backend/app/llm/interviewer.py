"""Interviewer agent context. Pure and importable: no LiveKit, no transport.

The worker in ``run_agent.py`` owns the voice pipeline; this module owns what the
interviewer is *told*, so evals can construct and inspect it without a room.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from .prompts import build_interviewer_instructions
from .schemas import InterviewContext

logger = logging.getLogger(__name__)

_TECH_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#.]*")

DEFAULT_JOB: dict[str, Any] = {
    "job_title": "Software Engineer",
    "qualifications": "Python experience",
}
DEFAULT_RESUME = "Experienced software engineer with Python and web development skills."


def parse_room_metadata(metadata: str | None) -> InterviewContext:
    """Read the job/resume the API stored on the room at creation time.

    Falls back to a generic context so a room created without metadata still
    produces a usable interview rather than crashing the worker.
    """
    if metadata:
        try:
            raw = json.loads(metadata)
            minutes = raw.get("max_minutes")
            return InterviewContext(
                job=raw.get("job") or DEFAULT_JOB,
                resume=raw.get("resume") or DEFAULT_RESUME,
                max_minutes=minutes if isinstance(minutes, int) and minutes > 0 else None,
            )
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Failed to parse room metadata, using defaults: %s", exc)

    return InterviewContext(job=DEFAULT_JOB, resume=DEFAULT_RESUME)


def build_instructions(context: InterviewContext) -> str:
    """The interviewer's system prompt for this session."""
    return build_interviewer_instructions(context.job, context.resume)


def technical_keywords(context: InterviewContext, *, limit: int = 50) -> list[str]:
    """STT vocabulary hints mined from this interview's job + resume.

    Every scoring decision downstream reads the transcript, and generic STT
    mangles niche technical terms ("PyPDF2" -> "pie PDF") — which the feedback
    model then blames on the candidate. Feeding the terms the candidate is
    *likely to say* to the STT keeps the transcript, and therefore the score,
    honest.

    ponytail: shape heuristic (internal caps / digits / +# / short acronyms),
    no NLP. Catches FastAPI/PyPDF2/GDPR/C++; an LLM extraction pass if resumes
    prove too plain-cased for it.
    """
    seen: dict[str, str] = {}

    # The candidate's name (usually the resume's first line): boosting it stops
    # the transcript calling them someone else ("Anwar" -> "Anurag").
    first_line = next((ln.strip() for ln in context.resume.splitlines() if ln.strip()), "")
    if len(first_line.split()) <= 5:
        for token in first_line.split():
            if token.isalpha() and token[0].isupper() and 2 <= len(token) <= 15:
                seen.setdefault(token.lower(), token)

    text = context.resume + " " + json.dumps(context.job)
    for token in _TECH_TOKEN_RE.findall(text):
        token = token.rstrip(".")
        if not 2 <= len(token) <= 30:
            continue
        if token.isupper():
            # Pure-alpha 2-letter acronyms hijack common words ("AI" swallows
            # "Hi"), so acronyms need 3+ letters; digit shorts (S3) stay.
            ok = 3 <= len(token) <= 6 or any(c.isdigit() for c in token)
        else:
            ok = (
                any(c.isupper() for c in token[1:])  # FastAPI, LangChain, PyTorch
                or any(c.isdigit() for c in token)   # PyPDF2, psycopg3, s3
                or "+" in token or "#" in token      # C++, C#
            )
        if ok:
            seen.setdefault(token.lower(), token)
        if len(seen) >= limit:  # over-boosting degrades general accuracy
            break
    return list(seen.values())
