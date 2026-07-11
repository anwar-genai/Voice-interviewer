"""Persist interview transcript turns + lifecycle status from the agent worker.

The worker is a separate process but shares ``DATABASE_URL``, so it writes
``Turn`` rows and updates ``Interview.status`` directly. It is best-effort: a DB
hiccup must never crash a live interview, so every write is guarded and only
logged on failure.

Events are duck-typed (``ev.item.role`` / ``ev.item.text_content`` / ``ev.reason``)
so this module — and therefore ``app.db`` — needs no LiveKit import; only the
worker ever calls ``attach_transcript_capture``.

ponytail: synchronous DB write per turn on the agent event loop. A voice turn is
seconds apart and an INSERT is milliseconds, so it doesn't stall turn-taking;
move to a background queue if transcript volume ever makes it matter.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select, update

from .models import Interview, Turn
from .session import session_scope

logger = logging.getLogger("interview.transcript")

# LiveKit chat roles -> the two roles we store. Anything else (e.g. "system") is
# not part of the interview transcript and is dropped.
_ROLE_MAP = {"user": "user", "assistant": "agent"}


def _lookup_interview_id(room_name: str) -> str | None:
    try:
        with session_scope() as db:
            return db.scalar(select(Interview.id).where(Interview.room == room_name))
    except Exception:
        logger.exception("Transcript: could not look up interview for room=%s", room_name)
        return None


def _write_turn(interview_id: str, role: str, content: str) -> None:
    try:
        with session_scope() as db:
            db.add(Turn(interview_id=interview_id, role=role, content=content))
    except Exception:
        logger.exception("Transcript: failed to persist %s turn for interview=%s", role, interview_id)


def _set_status(interview_id: str, status: str, room_name: str) -> None:
    try:
        with session_scope() as db:
            db.execute(update(Interview).where(Interview.id == interview_id).values(status=status))
        # Interview lifecycle event for the dashboards (Obs).
        logger.info("interview_lifecycle interview=%s room=%s status=%s", interview_id, room_name, status)
    except Exception:
        logger.exception("Transcript: failed to set status=%s for interview=%s", status, interview_id)


def attach_transcript_capture(session: Any, *, room_name: str) -> None:
    """Persist each conversation turn and the interview's lifecycle status.

    Looks the interview up once by room name; if there is no row (e.g. a room
    created without our metadata) transcript persistence is skipped rather than
    failing the session.
    """
    interview_id = _lookup_interview_id(room_name)
    if interview_id is None:
        logger.warning("No interview row for room=%s; transcript will not be persisted", room_name)
        return

    _set_status(interview_id, "in_progress", room_name)

    @session.on("conversation_item_added")
    def _on_item(ev: Any) -> None:
        role = _ROLE_MAP.get(getattr(ev.item, "role", None))
        text = (getattr(ev.item, "text_content", None) or "").strip()
        if role is None or not text:
            return
        _write_turn(interview_id, role, text)

    @session.on("close")
    def _on_close(ev: Any) -> None:
        # An error close is a dropped interview; any normal reason (user left,
        # task complete, job shutdown) is a completed one.
        status = "dropped" if getattr(ev, "reason", None) == "error" else "completed"
        _set_status(interview_id, status, room_name)
