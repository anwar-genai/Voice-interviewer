import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import APIRouter, Depends, HTTPException
from livekit import api as lk_api
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.auth import require_claims
from ..core.config import MissingConfigError, Settings, get_settings
from ..core.ratelimit import rate_limit
from ..db import get_db
from ..db.models import Interview, WorkerHeartbeat

logger = logging.getLogger("interview.agent")

router = APIRouter(prefix="/agent", tags=["agent"])


class JoinTokenRequest(BaseModel):
    # room and identity are derived server-side from the authenticated user and
    # are deliberately NOT accepted from the client.
    job: dict[str, Any] | None = None
    resume: str | None = None
    # The candidate must consent to voice recording + resume processing to start.
    consent: bool = False


# The worker beats every 30s; three missed beats = offline.
WORKER_ONLINE_WINDOW_SECONDS = 90


def _worker_online(db: Session) -> bool:
    row = db.get(WorkerHeartbeat, 1)
    if row is None:
        return False
    beat = row.beat_at
    if beat.tzinfo is None:  # SQLite (tests) stores naive UTC
        beat = beat.replace(tzinfo=timezone.utc)
    return beat >= datetime.now(timezone.utc) - timedelta(seconds=WORKER_ONLINE_WINDOW_SECONDS)


@router.get("/status")
async def agent_status(db: Session = Depends(get_db)):
    """Public: is a live interviewer (agent worker) available right now?

    The landing page uses this to offer the demo only when it can actually run.
    """
    return {"worker_online": _worker_online(db)}


def _enforce_cost_limits(
    db: Session, user_id: str, settings: Settings, is_guest: bool, exempt: bool = False
) -> None:
    """Cost controls (Phase 7): bound spend *before* a room or LLM call exists.

    Three COUNTs on the interviews table — DB-backed, so unlike the in-process
    rate limiter they survive restarts and hold across machines. "Active" rows
    age out of a time window instead of blocking forever (a crashed worker or a
    never-joined room strands status at created/in_progress; retention also
    sweeps those, but the window makes the check self-healing).

    Order matters: user-specific rejections (409/429) come before the global
    capacity check, so one user's verdict never depends on everyone else's load.
    """
    now = datetime.now(timezone.utc)
    window = now - timedelta(minutes=(settings.max_interview_minutes or 60) + 15)
    active = (
        Interview.status.in_(("created", "in_progress")),
        Interview.updated_at >= window,
    )

    def count(*where: Any) -> int:
        return db.scalar(select(func.count()).select_from(Interview).where(*where)) or 0

    if not exempt and count(Interview.user_id == user_id, *active):
        raise HTTPException(
            status_code=409,
            detail="You already have an interview in progress — finish it first, or discard it from History.",
        )

    if exempt:
        pass  # owner/personal use: no per-user quotas, global cap below still holds
    elif is_guest:
        # One demo interview per anonymous identity, ever. Only interviews that
        # actually started count, so an attempt the worker never joined doesn't
        # burn the guest's single slot.
        if count(Interview.user_id == user_id, Interview.status != "created"):
            raise HTTPException(
                status_code=429,
                detail="Your free demo interview has been used — create a free account to keep practicing.",
            )
    else:
        started_today = count(
            Interview.user_id == user_id,
            Interview.created_at >= now.replace(hour=0, minute=0, second=0, microsecond=0),
        )
        if started_today >= settings.daily_interview_limit:
            raise HTTPException(
                status_code=429,
                detail=f"Daily interview limit reached ({settings.daily_interview_limit} per day) — try again tomorrow.",
            )

    if count(*active) >= settings.max_concurrent_interviews:
        raise HTTPException(
            status_code=503,
            detail="All interview slots are in use right now — try again in a few minutes.",
        )


@router.post("/join-token")
async def create_join_token(
    body: JoinTokenRequest,
    user_id: str = Depends(rate_limit),
    claims: dict = Depends(require_claims),  # cached: same verification as rate_limit's
    db: Session = Depends(get_db),
):
    """Create the interview room, persist the interview, and mint a join token.

    Room and identity are derived from the authenticated user, never from the
    client. The interview (with the consent record) is saved so it survives
    restarts and belongs to the user.
    """
    if not body.consent:
        raise HTTPException(
            status_code=400,
            detail="Consent to voice recording and resume processing is required to start an interview.",
        )

    settings = get_settings()
    # Anonymous (no-signup demo) users get one short interview per day. A guest
    # can mint a fresh anonymous id by clearing storage, so the real backstops
    # are the global concurrency cap plus the short per-session time limit.
    # ponytail: IP-based throttling if demo abuse ever shows in the logs.
    is_guest = bool(claims.get("is_anonymous"))
    email = (claims.get("email") or "").lower()
    exempt = bool(email) and email in settings.unlimited_email_set
    _enforce_cost_limits(db, user_id, settings, is_guest=is_guest, exempt=exempt)

    # Never let a guest spend their one demo joining a room no interviewer will
    # ever enter (the worker runs on demand, not 24/7).
    if is_guest and not _worker_online(db):
        raise HTTPException(
            status_code=503,
            detail="The live interviewer is offline right now — request a demo session and try again later.",
        )

    try:
        livekit_url, api_key, api_secret = settings.require_livekit()
    except MissingConfigError:
        logger.error("LiveKit not configured")
        raise HTTPException(status_code=500, detail="Interview service is not configured")

    # Server owns room + identity; the client cannot pick either.
    room = f"interview-{uuid.uuid4()}"
    identity = user_id

    resume = (body.resume or "")[: settings.max_resume_chars]
    logger.info("consent_recorded user=%s scopes=voice,resume ts=%d", user_id, int(time.time()))

    # Pre-create the room with the job/resume in its metadata so the auto-dispatched
    # interview agent can personalize the session (it reads ctx.room.metadata on join).
    metadata = json.dumps(
        {
            "job": body.job or {},
            "resume": resume,
            "user_id": user_id,
            # Per-room session cap; the worker falls back to MAX_INTERVIEW_MINUTES.
            "max_minutes": settings.demo_interview_minutes if is_guest else None,
        }
    )
    try:
        async with lk_api.LiveKitAPI(livekit_url, api_key, api_secret) as lk:
            await lk.room.create_room(
                lk_api.CreateRoomRequest(
                    name=room,
                    metadata=metadata,
                    empty_timeout=settings.room_empty_timeout_seconds,
                )
            )
    except Exception:
        logger.exception("Failed to create interview room for user=%s", user_id)
        raise HTTPException(status_code=502, detail="Failed to create interview room")

    interview = Interview(
        user_id=user_id,
        room=room,
        status="created",
        job=body.job or {},
        resume=resume,
        consent_at=datetime.now(timezone.utc),
    )
    db.add(interview)
    db.commit()

    now = int(time.time())
    payload = {
        "iss": api_key,
        "exp": now + settings.join_token_ttl_seconds,
        "nbf": now - 5,
        "sub": identity,
        "name": identity,
        "video": {
            "room": room,
            "roomJoin": True,
            "canPublish": True,
            "canSubscribe": True,
        },
    }
    token = jwt.encode(payload, api_secret, algorithm="HS256")
    return {
        "url": livekit_url,
        "token": token,
        "room": room,
        "identity": identity,
        "interview_id": interview.id,
    }
