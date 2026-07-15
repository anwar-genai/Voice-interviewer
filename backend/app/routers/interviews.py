"""Interview history + erasure, scoped to the authenticated owner.

Replaces the old in-memory analytics dict: everything here is DB-backed and
filtered by ``user_id`` so one user can never see or delete another's data.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.auth import require_user
from ..db import get_db
from ..db.models import Interview

logger = logging.getLogger("interview.interviews")

router = APIRouter(prefix="/interviews", tags=["interviews"], dependencies=[Depends(require_user)])


class InterviewSummary(BaseModel):
    id: str
    room: str
    status: str
    job_title: str | None
    # None until the interview has been scored (Phase 3 feedback flow).
    overall_score: int | None
    created_at: datetime


class TurnOut(BaseModel):
    role: str  # "agent" | "user"
    content: str


class InterviewDetail(InterviewSummary):
    job: dict[str, Any]
    resume: str
    turns: list[TurnOut]
    share_token: str | None


def _summary(iv: Interview) -> InterviewSummary:
    return InterviewSummary(
        id=iv.id,
        room=iv.room,
        status=iv.status,
        job_title=(iv.job or {}).get("job_title"),
        # ponytail: lazy-loads feedback per row (N+1). Fine for one user's own
        # history; join/selectinload if a user ever has thousands of interviews.
        overall_score=iv.feedback.overall_score if iv.feedback else None,
        created_at=iv.created_at,
    )


def owned_or_404(db: Session, interview_id: str, user_id: str) -> Interview:
    """Fetch an interview the caller owns, or 404. Shared with the feedback router."""
    iv = db.get(Interview, interview_id)
    if iv is None or iv.user_id != user_id:
        # 404 (not 403) so we don't leak that someone else's interview exists.
        raise HTTPException(status_code=404, detail="Interview not found")
    return iv


@router.get("", response_model=list[InterviewSummary])
def list_interviews(user_id: str = Depends(require_user), db: Session = Depends(get_db)):
    """The caller's interviews, newest first."""
    rows = db.scalars(
        select(Interview).where(Interview.user_id == user_id).order_by(Interview.created_at.desc())
    ).all()
    return [_summary(iv) for iv in rows]


@router.get("/stats")
def interview_stats(user_id: str = Depends(require_user), db: Session = Depends(get_db)):
    """Counts over the caller's interviews (DB-backed, not an in-memory dict)."""
    total = db.scalar(
        select(func.count()).select_from(Interview).where(Interview.user_id == user_id)
    )
    by_status = db.execute(
        select(Interview.status, func.count())
        .where(Interview.user_id == user_id)
        .group_by(Interview.status)
    ).all()
    return {"total": total or 0, "by_status": {status: count for status, count in by_status}}


@router.delete("")
def delete_all_interviews(user_id: str = Depends(require_user), db: Session = Depends(get_db)):
    """Erase all of the caller's interviews (GDPR-style full deletion)."""
    rows = db.scalars(select(Interview).where(Interview.user_id == user_id)).all()
    for iv in rows:  # ponytail: ORM cascade delete; bulk delete + DB cascade if volume grows
        db.delete(iv)
    db.commit()
    return {"deleted": len(rows)}


@router.get("/{interview_id}", response_model=InterviewDetail)
def get_interview(
    interview_id: str, user_id: str = Depends(require_user), db: Session = Depends(get_db)
):
    iv = owned_or_404(db, interview_id, user_id)
    return InterviewDetail(
        **_summary(iv).model_dump(),
        job=iv.job or {},
        resume=iv.resume,
        turns=[TurnOut(role=t.role, content=t.content) for t in iv.turns],
        share_token=iv.share_token,
    )


@router.post("/{interview_id}/share")
def share_interview(
    interview_id: str, user_id: str = Depends(require_user), db: Session = Depends(get_db)
):
    """Mint (or return) the public share token for a scored interview."""
    iv = owned_or_404(db, interview_id, user_id)
    if iv.feedback is None:
        raise HTTPException(status_code=400, detail="Score the interview before sharing it")
    if iv.share_token is None:
        iv.share_token = secrets.token_urlsafe(16)  # 128-bit, unguessable
        db.commit()
    return {"token": iv.share_token}


@router.delete("/{interview_id}/share")
def unshare_interview(
    interview_id: str, user_id: str = Depends(require_user), db: Session = Depends(get_db)
):
    """Revoke the share link; the public URL 404s from now on."""
    iv = owned_or_404(db, interview_id, user_id)
    iv.share_token = None
    db.commit()
    return {"shared": False}


@router.delete("/{interview_id}")
def delete_interview(
    interview_id: str, user_id: str = Depends(require_user), db: Session = Depends(get_db)
):
    """Erase one interview and its turns + feedback (cascade)."""
    iv = owned_or_404(db, interview_id, user_id)
    db.delete(iv)
    db.commit()
    return {"deleted": 1}
