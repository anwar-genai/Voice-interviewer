"""Interviewer agent context. Pure and importable: no LiveKit, no transport.

The worker in ``run_agent.py`` owns the voice pipeline; this module owns what the
interviewer is *told*, so evals can construct and inspect it without a room.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .prompts import build_interviewer_instructions
from .schemas import InterviewContext

logger = logging.getLogger(__name__)

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
            return InterviewContext(
                job=raw.get("job") or DEFAULT_JOB,
                resume=raw.get("resume") or DEFAULT_RESUME,
            )
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Failed to parse room metadata, using defaults: %s", exc)

    return InterviewContext(job=DEFAULT_JOB, resume=DEFAULT_RESUME)


def build_instructions(context: InterviewContext) -> str:
    """The interviewer's system prompt for this session."""
    return build_interviewer_instructions(context.job, context.resume)
