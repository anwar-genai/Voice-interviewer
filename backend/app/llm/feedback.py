"""Interview feedback generation. Pure and importable: no FastAPI, no transport."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from .client import structured_completion
from .errors import InvalidInputError, LLMError
from .prompts import FEEDBACK_SCHEMA, build_feedback_messages
from .schemas import InterviewFeedback


def generate_feedback(
    *, job: dict[str, Any], resume: str, transcript: str
) -> InterviewFeedback:
    """Score a completed interview transcript against the feedback rubric."""
    if not transcript.strip():
        raise InvalidInputError("Interview transcript is empty")

    data = structured_completion(
        messages=build_feedback_messages(job, resume, transcript),
        schema=FEEDBACK_SCHEMA,
        schema_name="feedback_schema",
        temperature=0.3,
    )

    try:
        return InterviewFeedback(**data)
    except ValidationError as exc:
        raise LLMError(f"LLM returned feedback outside the rubric: {exc}") from exc
