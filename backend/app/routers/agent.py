import json
import time
import uuid

import jwt
from fastapi import APIRouter, HTTPException
from livekit import api as lk_api
from pydantic import BaseModel

from ..core.config import MissingConfigError, get_settings

router = APIRouter(prefix="/agent", tags=["agent"])


class JoinTokenRequest(BaseModel):
    room: str
    identity: str | None = None
    name: str | None = None
    job: dict | None = None
    resume: str | None = None


@router.post("/join-token")
async def create_join_token(body: JoinTokenRequest):
    """Create the interview room and mint a LiveKit join token for it.

    Phase 1 will derive `room` and `identity` server-side from the authenticated
    user instead of trusting the client.
    """
    settings = get_settings()
    try:
        livekit_url, api_key, api_secret = settings.require_livekit()
    except MissingConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Pre-create the room with the job/resume in its metadata so the auto-dispatched
    # interview agent can personalize the session (it reads ctx.room.metadata on join).
    metadata = json.dumps({"job": body.job or {}, "resume": body.resume or ""})
    try:
        async with lk_api.LiveKitAPI(livekit_url, api_key, api_secret) as lk:
            await lk.room.create_room(
                lk_api.CreateRoomRequest(
                    name=body.room,
                    metadata=metadata,
                    empty_timeout=settings.room_empty_timeout_seconds,
                )
            )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Failed to create interview room: {exc}")

    identity = body.identity or str(uuid.uuid4())
    now = int(time.time())

    payload = {
        "iss": api_key,
        "exp": now + settings.join_token_ttl_seconds,
        "nbf": now - 5,
        "sub": identity,
        "name": body.name or identity,
        "video": {
            "room": body.room,
            "roomJoin": True,
            "canPublish": True,
            "canSubscribe": True,
        },
    }

    token = jwt.encode(payload, api_secret, algorithm="HS256")
    return {"url": livekit_url, "token": token, "identity": identity}
