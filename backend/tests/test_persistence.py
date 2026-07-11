"""Phase 2 persistence checks: ownership scoping, cascade erasure, retention.

Runs on an in-memory SQLite DB (no Supabase needed), exercising the ORM
relationships and the retention logic.

    python tests/test_persistence.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db import Base  # noqa: E402
from app.db.models import Feedback, Interview, Turn  # noqa: E402
from app.db.retention import purge_expired_interviews  # noqa: E402


def _session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_owner_scoping_isolates_users() -> None:
    db = _session()
    db.add(Interview(user_id="u1", room="r1"))
    db.add(Interview(user_id="u2", room="r2"))
    db.commit()

    u1 = db.scalars(select(Interview).where(Interview.user_id == "u1")).all()
    assert len(u1) == 1 and u1[0].room == "r1", "a user must only see their own interviews"


def test_erasure_cascades_to_turns_and_feedback() -> None:
    db = _session()
    iv = Interview(user_id="u1", room="r1", job={"job_title": "SWE"}, resume="cv")
    iv.turns = [Turn(role="agent", content="hi"), Turn(role="user", content="hello")]
    iv.feedback = Feedback(
        strengths=["s"], improvements=["i"], recommendations=["r"],
        overall_score=8, technical_score=7, communication_score=9,
    )
    db.add(iv)
    db.commit()

    assert db.scalar(select(func.count()).select_from(Turn)) == 2

    db.delete(iv)
    db.commit()
    assert db.scalar(select(func.count()).select_from(Interview)) == 0
    assert db.scalar(select(func.count()).select_from(Turn)) == 0, "turns must be erased with the interview"
    assert db.scalar(select(func.count()).select_from(Feedback)) == 0, "feedback must be erased too"


def test_retention_purges_only_expired() -> None:
    db = _session()
    now = datetime.now(timezone.utc)
    db.add(Interview(user_id="u1", room="old", created_at=now - timedelta(days=40)))
    db.add(Interview(user_id="u1", room="fresh", created_at=now))
    db.commit()

    removed = purge_expired_interviews(db, older_than_days=30)
    assert removed == 1, removed
    remaining = db.scalars(select(Interview)).all()
    assert len(remaining) == 1 and remaining[0].room == "fresh"


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"OK  {t.__name__}")
    print(f"\nAll {len(tests)} persistence checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
