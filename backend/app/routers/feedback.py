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
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
from ..observability.tracing import current_interview_id
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


def save_feedback(db: Session, interview_id: str, feedback: InterviewFeedback) -> InterviewFeedback:
    """Persist the scores; if a concurrent request won the race, return theirs.

    Two requests can both pass the ``feedback is None`` check (double-click on
    End Interview, two tabs); unique(interview_id) catches the loser here.

    ponytail: the loser still paid for one extra LLM call in that window; a row
    lock would fix that but means holding a DB transaction across an LLM call —
    not worth it while this runs single-worker.
    """
    db.add(Feedback(interview_id=interview_id, **feedback.model_dump()))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        row = db.scalar(select(Feedback).where(Feedback.interview_id == interview_id))
        if row is None:  # constraint violation but no winner row: a real fault
            raise
        return _as_feedback(row)
    return feedback


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
    current_interview_id.set(iv.id)  # correlate this request's llm_trace lines
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

    return save_feedback(db, iv.id, feedback)


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
