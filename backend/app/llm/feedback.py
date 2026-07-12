"""Interview feedback generation. Pure and importable: no FastAPI, no transport."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from ..observability.redaction import redact
from .client import structured_completion
from .errors import InvalidInputError, LLMError
from .guardrails import candidate_names
from .prompts import FEEDBACK_SCHEMA, build_feedback_messages
from .schemas import InterviewFeedback


def generate_feedback(
    *, job: dict[str, Any], resume: str, transcript: str, temperature: float = 0.3
) -> InterviewFeedback:
    """Score a completed interview transcript against the feedback rubric.

    ``temperature`` exists for the eval harness: fairness counterfactuals score
    at 0 so a score delta is signal, not sampling noise.
    """
    if not transcript.strip():
        raise InvalidInputError("Interview transcript is empty")

    # Fairness by construction: the scorer never sees the candidate's name (a
    # gender/ethnicity proxy that measurably moved scores — evals/fairness
    # verifies this end to end). redact() also strips emails/phones, which is
    # data minimization toward the provider for free.
    names = candidate_names(resume)
    resume = redact(resume, names=names)
    transcript = redact(transcript, names=names)

    data = structured_completion(
        messages=build_feedback_messages(job, resume, transcript),
        schema=FEEDBACK_SCHEMA,
        schema_name="feedback_schema",
        temperature=temperature,
    )

    try:
        return InterviewFeedback(**data)
    except ValidationError as exc:
        raise LLMError(f"LLM returned feedback outside the rubric: {exc}") from exc
