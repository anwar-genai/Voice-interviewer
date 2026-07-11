"""Feedback: score a completed interview from its persisted transcript.

The transcript now lives in the DB (captured by the agent worker), so the client
sends only an ``interview_id``; the server loads the turns, scores them once, and
stores the result. Generation is idempotent — a second call returns the saved
feedback rather than re-billing the LLM.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.auth import require_user
from ..core.config import MissingConfigError
from ..core.ratelimit import rate_limit
from ..db import get_db
from ..db.models import Feedback
from ..llm import (
    InterviewFeedback,
    InvalidInputError,
    LLMError,
    generate_feedback,
    require_groundable_transcript,
)
from .interviews import owned_or_404

logger = logging.getLogger("interview.feedback")

# Every feedback endpoint requires an authenticated user.
router = APIRouter(prefix="/feedback", tags=["feedback"], dependencies=[Depends(require_user)])

_ROLE_LABEL = {"agent": "Interviewer", "user": "Candidate"}


class GenerateFeedbackRequest(BaseModel):
    interview_id: str


def _as_feedback(row: Feedback) -> InterviewFeedback:
    return InterviewFeedback(
        strengths=row.strengths,
        improvements=row.improvements,
        recommendations=row.recommendations,
        overall_score=row.overall_score,
        technical_score=row.technical_score,
        communication_score=row.communication_score,
    )


def build_transcript(turns: list[Any]) -> tuple[str, str]:
    """Assemble the labelled transcript and the candidate-only text from turns.

    Returns ``(transcript, candidate_text)`` — the first for the feedback prompt,
    the second for the groundedness guard.
    """
    transcript = "\n".join(f"{_ROLE_LABEL[t.role]}: {t.content}" for t in turns if t.role in _ROLE_LABEL)
    candidate_text = " ".join(t.content for t in turns if t.role == "user")
    return transcript, candidate_text


@router.post("/generate", response_model=InterviewFeedback)
def generate_interview_feedback(
    request: GenerateFeedbackRequest,
    user_id: str = Depends(rate_limit),
    db: Session = Depends(get_db),
):
    """Score a completed interview against the feedback rubric, once, and store it."""
    iv = owned_or_404(db, request.interview_id, user_id)
    if iv.feedback is not None:
        return _as_feedback(iv.feedback)  # idempotent: don't re-bill the LLM

    transcript, candidate_text = build_transcript(iv.turns)

    try:
        # Groundedness: refuse to score a transcript with too little candidate
        # speech instead of letting the model invent strengths.
        require_groundable_transcript(candidate_text)
        feedback = generate_feedback(job=iv.job or {}, resume=iv.resume, transcript=transcript)
    except InvalidInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except MissingConfigError:
        logger.error("LLM not configured")
        raise HTTPException(status_code=500, detail="Feedback service is not configured")
    except LLMError:
        logger.exception("Feedback generation failed")
        raise HTTPException(status_code=502, detail="Feedback service failed")

    db.add(Feedback(interview_id=iv.id, **feedback.model_dump()))
    db.commit()
    return feedback


@router.get("/{interview_id}", response_model=InterviewFeedback)
def get_interview_feedback(
    interview_id: str,
    user_id: str = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Return the stored feedback for an interview, or 404 if it hasn't been scored."""
    iv = owned_or_404(db, interview_id, user_id)
    if iv.feedback is None:
        raise HTTPException(status_code=404, detail="This interview has not been scored yet")
    return _as_feedback(iv.feedback)


class InterviewMetrics(BaseModel):
    total_questions: int
    response_time_avg: float
    technical_depth: int
    communication_clarity: int
    engagement_level: int


class MetricsRequest(BaseModel):
    transcript: str


@router.post("/metrics", response_model=InterviewMetrics)
def calculate_interview_metrics(request: MetricsRequest):
    """Cheap heuristic counts over a transcript. No LLM involved."""
    transcript = request.transcript
    words = transcript.split()
    sentences = [s for s in transcript.split(".") if s.strip()]

    return InterviewMetrics(
        total_questions=transcript.count("?"),
        response_time_avg=len(words) / max(len(sentences), 1) * 0.5,
        technical_depth=min(
            10,
            transcript.count("technical") + transcript.count("experience") + transcript.count("project"),
        ),
        communication_clarity=min(
            10,
            transcript.count("explain") + transcript.count("describe") + transcript.count("example"),
        ),
        engagement_level=min(
            10,
            transcript.count("yes") + transcript.count("absolutely") + transcript.count("definitely"),
        ),
    )
