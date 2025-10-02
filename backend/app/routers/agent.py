import os
import time
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import jwt


router = APIRouter(prefix="/agent", tags=["agent"])


class StartAgentRequest(BaseModel):
    candidate_text: str
    job_context: dict


@router.post("/start")
async def start_agent(_: StartAgentRequest):
    # Placeholder: In a production system you would initialize LiveKit worker/session here
    # and return a join token or a websocket URL for the frontend to connect.
    livekit_url = os.getenv("LIVEKIT_URL") or os.getenv("LiveKit_URL")
    if not livekit_url:
        raise HTTPException(status_code=500, detail="LiveKit_URL not configured")
    return {"room_wss": livekit_url}


class JoinTokenRequest(BaseModel):
    room: str
    identity: str | None = None
    name: str | None = None


@router.post("/join-token")
def create_join_token(body: JoinTokenRequest):
    api_key = os.getenv("LIVEKIT_API_KEY") or os.getenv("LiveKit_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET") or os.getenv("LiveKit_API_SECRET")
    livekit_url = os.getenv("LIVEKIT_URL") or os.getenv("LiveKit_URL")
    if not api_key or not api_secret or not livekit_url:
        raise HTTPException(status_code=500, detail="LiveKit environment not configured")

    identity = body.identity or str(uuid.uuid4())
    now = int(time.time())
    exp = now + 60 * 60  # 1 hour

    # LiveKit access token payload
    payload = {
        "iss": api_key,
        "exp": exp,
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


