"""Phase 3 checks: transcript capture, feedback wiring, groundedness guard,
outage buffering, stale-interview sweeping, and the feedback write race.

Runs on in-memory SQLite (no Supabase, no LLM). The transcript-capture tests
drive ``attach_transcript_capture`` with a fake AgentSession and the writer
thread patched to run inline, so they exercise the real persistence + lifecycle
logic without a live voice pipeline.

    python tests/test_phase3.py
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bootstrap  # noqa: E402

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.db import Base  # noqa: E402
from app.db.models import Feedback, Interview, Turn  # noqa: E402
from app.db.retention import mark_stale_in_progress  # noqa: E402
from app.llm import InterviewFeedback, InvalidInputError, require_groundable_transcript  # noqa: E402
from app.routers.feedback import _as_feedback, build_transcript, save_feedback  # noqa: E402


class _FakeSession:
    """Minimal stand-in for AgentSession: records .on() handlers, emits to them."""

    def __init__(self) -> None:
        self._handlers: dict[str, list] = {}

    def on(self, event: str):
        def deco(fn):
            self._handlers.setdefault(event, []).append(fn)
            return fn
        return deco

    def emit(self, event: str, payload) -> None:
        for fn in self._handlers.get(event, []):
            fn(payload)


def _sqlite_factory() -> sessionmaker[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _turn(role: str, text: str) -> SimpleNamespace:
    return SimpleNamespace(item=SimpleNamespace(role=role, text_content=text))


# --- groundedness guard ----------------------------------------------------

def test_guard_rejects_thin_transcript() -> None:
    try:
        require_groundable_transcript("um, not sure")
        raise AssertionError("guard should reject a near-empty candidate transcript")
    except InvalidInputError:
        pass


def test_guard_passes_substantive_transcript() -> None:
    require_groundable_transcript("I built a payments API on FastAPI and Postgres " * 3)


# --- feedback assembly + persistence ----------------------------------------

def test_build_transcript_labels_and_extracts_candidate() -> None:
    turns = [
        SimpleNamespace(role="agent", content="Tell me about yourself."),
        SimpleNamespace(role="user", content="I am a backend engineer."),
        SimpleNamespace(role="system", content="internal note"),  # dropped
    ]
    transcript, candidate_text = build_transcript(turns)
    assert "Interviewer: Tell me about yourself." in transcript
    assert "Candidate: I am a backend engineer." in transcript
    assert "internal note" not in transcript, "system turns must not enter the transcript"
    assert candidate_text == "I am a backend engineer."


def test_as_feedback_maps_row_to_schema() -> None:
    row = Feedback(
        interview_id="x", strengths=["s"], improvements=["i"], recommendations=["r"],
        overall_score=8, technical_score=7, communication_score=9,
    )
    fb = _as_feedback(row)
    assert fb.overall_score == 8 and fb.technical_score == 7 and fb.communication_score == 9
    assert fb.strengths == ["s"] and fb.recommendations == ["r"]


def test_duplicate_feedback_returns_winner() -> None:
    """Two racing generate calls: the loser gets the winner's row, not a 500."""
    db = _sqlite_factory()()
    iv = Interview(user_id="u1", room="fb-race")
    db.add(iv)
    db.commit()

    def _fb(score: int) -> InterviewFeedback:
        return InterviewFeedback(
            strengths=["s"], improvements=["i"], recommendations=["r"],
            overall_score=score, technical_score=5, communication_score=5,
        )

    assert save_feedback(db, iv.id, _fb(7)).overall_score == 7
    assert save_feedback(db, iv.id, _fb(2)).overall_score == 7, "loser must return the winner's scores"
    assert db.scalar(select(func.count()).select_from(Feedback)) == 1, "exactly one feedback row"


# --- transcript capture (worker path) --------------------------------------

def _capture_env(monkeypatch, room: str):
    """Wire attach_transcript_capture to SQLite with the writer thread inlined.

    Returns (fake_session, scope, down) where flipping down['on'] simulates a
    DB outage for every subsequent write.
    """
    from app.db import transcript as tx

    factory = _sqlite_factory()
    down = {"on": False}

    @contextmanager
    def scope():
        if down["on"]:
            raise RuntimeError("db down")
        db = factory()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    monkeypatch.setattr(tx, "session_scope", scope)
    monkeypatch.setattr(tx, "_submit", lambda fn, *a: fn(*a))  # writer thread -> inline

    with scope() as db:
        db.add(Interview(user_id="u1", room=room, status="created"))

    fake = _FakeSession()
    tx.attach_transcript_capture(fake, room_name=room)
    return fake, scope, down


def test_capture_persists_turns_and_lifecycle(monkeypatch) -> None:
    fake, scope, _ = _capture_env(monkeypatch, "interview-abc")

    # status should have moved to in_progress on attach
    with scope() as db:
        iv = db.scalar(select(Interview).where(Interview.room == "interview-abc"))
        assert iv.status == "in_progress", iv.status
        interview_id = iv.id

    # an agent turn, a user turn, an empty user turn (skipped), a system turn (skipped)
    fake.emit("conversation_item_added", _turn("assistant", "Hello!"))
    fake.emit("conversation_item_added", _turn("user", "Hi there."))
    fake.emit("conversation_item_added", _turn("user", "   "))
    fake.emit("conversation_item_added", _turn("system", "ignored"))

    with scope() as db:
        turns = db.scalars(select(Turn).order_by(Turn.created_at)).all()
        assert [(t.role, t.content) for t in turns] == [("agent", "Hello!"), ("user", "Hi there.")], turns
        assert all(t.interview_id == interview_id for t in turns)

    # a normal close completes the interview
    fake.emit("close", SimpleNamespace(reason="user_initiated"))
    with scope() as db:
        iv = db.scalar(select(Interview).where(Interview.room == "interview-abc"))
        assert iv.status == "completed", iv.status


def test_capture_buffers_turns_through_db_outage(monkeypatch) -> None:
    """Turns emitted while the DB is down are buffered and flushed on recovery."""
    fake, scope, down = _capture_env(monkeypatch, "interview-outage")

    down["on"] = True  # DB goes away mid-interview
    fake.emit("conversation_item_added", _turn("assistant", "First question?"))
    fake.emit("conversation_item_added", _turn("user", "First answer."))

    down["on"] = False  # DB back; nothing was written yet
    with scope() as db:
        assert db.scalar(select(func.count()).select_from(Turn)) == 0

    # next turn flushes the buffer too, in event order
    fake.emit("conversation_item_added", _turn("user", "Second answer."))
    with scope() as db:
        turns = db.scalars(select(Turn).order_by(Turn.created_at)).all()
        assert [t.content for t in turns] == ["First question?", "First answer.", "Second answer."], turns

    fake.emit("close", SimpleNamespace(reason="participant_disconnected"))
    with scope() as db:
        iv = db.scalar(select(Interview).where(Interview.room == "interview-outage"))
        assert iv.status == "completed", iv.status


# --- lifecycle sweeper -------------------------------------------------------

def test_sweeper_marks_stale_in_progress_dropped() -> None:
    db = _sqlite_factory()()
    now = datetime.now(timezone.utc)
    db.add(Interview(user_id="u1", room="stale", status="in_progress", updated_at=now - timedelta(hours=7)))
    db.add(Interview(user_id="u1", room="live", status="in_progress", updated_at=now))
    db.add(Interview(user_id="u1", room="done", status="completed", updated_at=now - timedelta(hours=48)))
    db.commit()

    assert mark_stale_in_progress(db, older_than_hours=6) == 1
    status = {iv.room: iv.status for iv in db.scalars(select(Interview)).all()}
    assert status == {"stale": "dropped", "live": "in_progress", "done": "completed"}, status


if __name__ == "__main__":
    raise SystemExit(_bootstrap.run_as_script(globals(), "Phase 3"))
