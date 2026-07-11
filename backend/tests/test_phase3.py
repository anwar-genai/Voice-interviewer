"""Phase 3 checks: transcript capture, feedback wiring, groundedness guard.

Runs on in-memory SQLite (no Supabase, no LLM). The transcript-capture test
drives ``attach_transcript_capture`` with a fake AgentSession and a session
scope pointed at SQLite, so it exercises the real turn-persistence + lifecycle
logic without a live voice pipeline.

    python tests/test_phase3.py
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.db import Base  # noqa: E402
from app.db.models import Feedback, Interview, Turn  # noqa: E402
from app.llm import InvalidInputError, require_groundable_transcript  # noqa: E402
from app.routers.feedback import _as_feedback, build_transcript  # noqa: E402


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


# --- groundedness guard ----------------------------------------------------

def test_guard_rejects_thin_transcript() -> None:
    try:
        require_groundable_transcript("um, not sure")
        raise AssertionError("guard should reject a near-empty candidate transcript")
    except InvalidInputError:
        pass


def test_guard_passes_substantive_transcript() -> None:
    require_groundable_transcript("I built a payments API on FastAPI and Postgres " * 3)


# --- feedback assembly -----------------------------------------------------

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


# --- transcript capture (worker path) --------------------------------------

def test_capture_persists_turns_and_lifecycle(monkeypatch) -> None:
    from app.db import transcript as tx

    factory = _sqlite_factory()

    @contextmanager
    def fake_scope():
        db = factory()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    monkeypatch.setattr(tx, "session_scope", fake_scope)

    with fake_scope() as db:
        db.add(Interview(user_id="u1", room="interview-abc", status="created"))

    fake = _FakeSession()
    tx.attach_transcript_capture(fake, room_name="interview-abc")

    # status should have moved to in_progress on attach
    with fake_scope() as db:
        iv = db.scalar(select(Interview).where(Interview.room == "interview-abc"))
        assert iv.status == "in_progress", iv.status
        interview_id = iv.id

    # emit an agent turn, a user turn, an empty user turn (skipped), a system turn (skipped)
    fake.emit("conversation_item_added", SimpleNamespace(item=SimpleNamespace(role="assistant", text_content="Hello!")))
    fake.emit("conversation_item_added", SimpleNamespace(item=SimpleNamespace(role="user", text_content="Hi there.")))
    fake.emit("conversation_item_added", SimpleNamespace(item=SimpleNamespace(role="user", text_content="   ")))
    fake.emit("conversation_item_added", SimpleNamespace(item=SimpleNamespace(role="system", text_content="ignored")))

    with fake_scope() as db:
        turns = db.scalars(select(Turn).where(Turn.interview_id == interview_id).order_by(Turn.created_at)).all()
        assert [(t.role, t.content) for t in turns] == [("agent", "Hello!"), ("user", "Hi there.")], turns

    # a normal close completes the interview
    fake.emit("close", SimpleNamespace(reason="user_initiated"))
    with fake_scope() as db:
        iv = db.scalar(select(Interview).where(Interview.room == "interview-abc"))
        assert iv.status == "completed", iv.status


# --- minimal monkeypatch shim (no pytest dependency) -----------------------

class _MonkeyPatch:
    def __init__(self) -> None:
        self._undo: list = []

    def setattr(self, target, name, value) -> None:
        old = getattr(target, name)
        self._undo.append((target, name, old))
        setattr(target, name, value)

    def undo(self) -> None:
        for target, name, old in reversed(self._undo):
            setattr(target, name, old)


def main() -> int:
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for name, fn in tests:
        mp = _MonkeyPatch()
        try:
            if fn.__code__.co_argcount:
                fn(mp)
            else:
                fn()
        finally:
            mp.undo()
        print(f"OK  {name}")
    print(f"\nAll {len(tests)} Phase 3 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
