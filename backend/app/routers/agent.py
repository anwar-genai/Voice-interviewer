import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import jwt
from fastapi import APIRouter, Depends, HTTPException
from livekit import api as lk_api
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.config import MissingConfigError, get_settings
from ..core.ratelimit import rate_limit
from ..db import get_db
from ..db.models import Interview

logger = logging.getLogger("interview.agent")

router = APIRouter(prefix="/agent", tags=["agent"])


class JoinTokenRequest(BaseModel):
    # room and identity are derived server-side from the authenticated user and
    # are deliberately NOT accepted from the client.
    job: dict[str, Any] | None = None
    resume: str | None = None
    # The candidate must consent to voice recording + resume processing to start.
    consent: bool = False


@router.post("/join-token")
async def create_join_token(
    body: JoinTokenRequest,
    user_id: str = Depends(rate_limit),
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
    metadata = json.dumps({"job": body.job or {}, "resume": resume, "user_id": user_id})
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
