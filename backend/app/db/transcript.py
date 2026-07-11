"""Persist interview transcript turns + lifecycle status from the agent worker.

The worker is a separate process but shares ``DATABASE_URL``, so it writes
``Turn`` rows and updates ``Interview.status`` directly. It is best-effort: a DB
hiccup must never crash — or stall — a live interview:

- Every write runs on ONE dedicated writer thread (never the voice event loop),
  so a slow database can't freeze turn-taking. A single thread also serializes
  writes, which preserves turn order for free.
- A failed turn write is buffered in memory and re-flushed with the next write
  (or at session close), so a transient DB outage doesn't lose the transcript.
- ``created_at`` is captured when the event fires, not when the row lands, so
  ordering survives buffering and retries.

Events are duck-typed (``ev.item.role`` / ``ev.item.text_content`` / ``ev.reason``)
so this module — and therefore ``app.db`` — needs no LiveKit import; only the
worker ever calls ``attach_transcript_capture``.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import select, update

from .models import Interview, Turn
from .session import session_scope

logger = logging.getLogger("interview.transcript")

# LiveKit chat roles -> the two roles we store. Anything else (e.g. "system") is
# not part of the interview transcript and is dropped.
_ROLE_MAP = {"user": "user", "assistant": "agent"}

# ponytail: one writer thread for the whole worker process. Serializes all
# transcript writes across sessions; a queue per session if a worker ever hosts
# enough concurrent interviews for one thread to back up.
_writer = ThreadPoolExecutor(max_workers=1, thread_name_prefix="transcript")


def _submit(fn: Callable[..., None], *args: Any) -> None:
    """Run a DB write on the writer thread. Every ``fn`` catches its own errors."""
    _writer.submit(fn, *args)


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

    The interview is looked up by room name on the writer thread; if there is no
    row (e.g. a room created without our metadata) every later write is a no-op
    rather than a failure.
    """
    # Only ever touched by the single writer thread -> no locking needed.
    state: dict[str, Any] = {"interview_id": None, "pending": []}

    def _flush(extra: tuple[tuple[str, str, datetime], ...] = ()) -> None:
        """Write buffered + new turns in one transaction; on failure, keep them."""
        interview_id = state["interview_id"]
        if interview_id is None:
            return
        batch = state["pending"] + list(extra)
        if not batch:
            return
        try:
            with session_scope() as db:
                for role, content, at in batch:
                    db.add(Turn(interview_id=interview_id, role=role, content=content, created_at=at))
            state["pending"] = []
        except Exception:
            state["pending"] = batch  # retried on the next turn or at close
            logger.exception(
                "Transcript: DB write failed; buffering %d turn(s) for interview=%s",
                len(batch),
                interview_id,
            )

    def _init() -> None:
        try:
            with session_scope() as db:
                state["interview_id"] = db.scalar(
                    select(Interview.id).where(Interview.room == room_name)
                )
        except Exception:
            logger.exception("Transcript: could not look up interview for room=%s", room_name)
        if state["interview_id"] is None:
            logger.warning("No interview row for room=%s; transcript will not be persisted", room_name)
            return
        _set_status(state["interview_id"], "in_progress", room_name)

    def _finish(status: str) -> None:
        _flush()  # last chance for anything buffered; failure is logged inside
        if state["interview_id"] is not None:
            _set_status(state["interview_id"], status, room_name)

    _submit(_init)

    @session.on("conversation_item_added")
    def _on_item(ev: Any) -> None:
        role = _ROLE_MAP.get(getattr(ev.item, "role", None))
        text = (getattr(ev.item, "text_content", None) or "").strip()
        if role is None or not text:
            return
        # Timestamp at event time so ordering survives buffering/retries.
        _submit(_flush, ((role, text, datetime.now(timezone.utc)),))

    @session.on("close")
    def _on_close(ev: Any) -> None:
        # An error close is a dropped interview; any normal reason (user left,
        # task complete, job shutdown) is a completed one.
        status = "dropped" if getattr(ev, "reason", None) == "error" else "completed"
        _submit(_finish, status)
