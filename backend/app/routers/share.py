"""Public read-only feedback shares: ``GET /share/{token}`` needs no auth.

Deliberately exposes only the scores/feedback and the job title — never the
transcript, résumé, or owner identity. Revoking the token (or deleting the
interview) kills the link.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..db.models import Interview
from ..llm import InterviewFeedback
from .feedback import _as_feedback

router = APIRouter(prefix="/share", tags=["share"])


class SharedReport(BaseModel):
    job_title: str | None
    created_at: datetime
    feedback: InterviewFeedback


@router.get("/{token}", response_model=SharedReport)
def get_shared_report(token: str, db: Session = Depends(get_db)):
    # ponytail: no rate limit here — the 128-bit token is the defense; add one
    # (keyed by client IP) if scanning ever shows up in the logs.
    iv = db.scalar(select(Interview).where(Interview.share_token == token))
    if iv is None or iv.feedback is None:
        raise HTTPException(status_code=404, detail="This shared report does not exist or was unshared")
    return SharedReport(
        job_title=(iv.job or {}).get("job_title"),
        created_at=iv.created_at,
        feedback=_as_feedback(iv.feedback),
    )
