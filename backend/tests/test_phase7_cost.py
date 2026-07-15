"""Phase 7 cost controls: quota, one-active-per-user, global capacity, extraction cache.

Every rejection fires *before* the LiveKit/LLM call, so none of this needs a
provider mock — a blocked request never reaches the paid path. Interviews are
seeded straight into the DB and each test makes exactly one HTTP call (the
per-user rate limit is 3/min in tests).

    python tests/test_phase7_cost.py        (or: python -m pytest)
"""

from __future__ import annotations

import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bootstrap  # noqa: E402

_bootstrap.bootstrap()  # env + throwaway DB, BEFORE importing the app

import jwt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.llm.extraction as extraction  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.models import Interview  # noqa: E402
from app.db.session import session_scope  # noqa: E402
from app.llm.errors import LLMError  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)

START = {"consent": True, "job": {"job_title": "Backend Engineer"}, "resume": "resume text"}


def _auth(sub: str, *, anonymous: bool = False) -> dict[str, str]:
    claims = {"sub": sub, "aud": "authenticated", "exp": int(time.time()) + 3600}
    if anonymous:
        claims["is_anonymous"] = True
    token = jwt.encode(claims, _bootstrap.TEST_JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _seed(user_id: str, *, status: str = "completed", created_at: datetime | None = None) -> None:
    with session_scope() as db:
        iv = Interview(user_id=user_id, room=f"room-{uuid.uuid4()}", status=status)
        if created_at is not None:
            iv.created_at = iv.updated_at = created_at
        db.add(iv)


def _clear_active() -> None:
    """Complete any active rows other suites left in the shared test DB, so
    'passes the cost gate' assertions don't depend on suite-wide state."""
    with session_scope() as db:
        for iv in db.query(Interview).filter(Interview.status.in_(("created", "in_progress"))):
            iv.status = "completed"


# --- /agent/join-token cost gates ---------------------------------------------

def test_daily_quota_blocks_after_limit() -> None:
    # DAILY_INTERVIEW_LIMIT=2 in tests; outcome doesn't matter, started-today does.
    _seed("p7-quota-user")
    _seed("p7-quota-user")
    r = client.post("/agent/join-token", json=START, headers=_auth("p7-quota-user"))
    assert r.status_code == 429, (r.status_code, r.text)
    assert "limit" in r.json()["detail"].lower()


def test_yesterdays_interviews_do_not_count(monkeypatch) -> None:
    # Blank LiveKit config so "past the cost gates" is a deterministic 500 —
    # never a real room (a local .env has real credentials).
    monkeypatch.setattr(get_settings(), "livekit_url", None)
    _clear_active()
    old = datetime.now(timezone.utc) - timedelta(days=2)
    _seed("p7-fresh-user", created_at=old)
    _seed("p7-fresh-user", created_at=old)
    r = client.post("/agent/join-token", json=START, headers=_auth("p7-fresh-user"))
    assert r.status_code == 500, (r.status_code, r.text)  # past the gates, stopped by config only


def test_second_concurrent_interview_is_rejected() -> None:
    _seed("p7-active-user", status="in_progress")
    r = client.post("/agent/join-token", json=START, headers=_auth("p7-active-user"))
    assert r.status_code == 409, (r.status_code, r.text)


def test_global_capacity_returns_503() -> None:
    # MAX_CONCURRENT_INTERVIEWS=3 in tests; fill the slots with other users.
    for i in range(3):
        _seed(f"p7-crowd-{i}", status="in_progress")
    r = client.post("/agent/join-token", json=START, headers=_auth("p7-capacity-user"))
    assert r.status_code == 503, (r.status_code, r.text)


def test_stale_active_rows_age_out(monkeypatch) -> None:
    # A crashed worker strands in_progress rows; hours later they must not block.
    monkeypatch.setattr(get_settings(), "livekit_url", None)
    _clear_active()
    stale = datetime.now(timezone.utc) - timedelta(hours=6)
    _seed("p7-stale-user", status="in_progress", created_at=stale)
    r = client.post("/agent/join-token", json=START, headers=_auth("p7-stale-user"))
    assert r.status_code == 500, (r.status_code, r.text)  # past the gates, stopped by config only


# --- anonymous (no-signup demo) guests -----------------------------------------

def test_guest_gets_one_interview_per_day() -> None:
    # DAILY_INTERVIEW_LIMIT=2 in tests, but anonymous users are capped at 1.
    _seed("p7-guest-user")
    r = client.post("/agent/join-token", json=START, headers=_auth("p7-guest-user", anonymous=True))
    assert r.status_code == 429, (r.status_code, r.text)


def test_guest_rooms_carry_demo_time_cap() -> None:
    from app.llm import parse_room_metadata

    ctx = parse_room_metadata('{"job": {}, "resume": "r", "max_minutes": 5}')
    assert ctx.max_minutes == 5
    # Regular rooms (None) and garbage values fall back to the global setting.
    assert parse_room_metadata('{"job": {}, "resume": "r", "max_minutes": null}').max_minutes is None
    assert parse_room_metadata('{"job": {}, "resume": "r", "max_minutes": -3}').max_minutes is None
    assert parse_room_metadata('{"job": {}, "resume": "r", "max_minutes": "9"}').max_minutes is None


# --- /utils extraction cache ---------------------------------------------------

def test_repeat_jd_parse_hits_cache(monkeypatch) -> None:
    calls = {"n": 0}

    def fake_completion(**kwargs):
        calls["n"] += 1
        return {"job title": "Backend Engineer"}

    monkeypatch.setattr(extraction, "structured_completion", fake_completion)
    text = f"Backend Engineer role, unique token {uuid.uuid4()}."

    r1 = client.post("/utils/parse-job-text-llm", json={"text": text}, headers=_auth("p7-cache-user"))
    r2 = client.post("/utils/parse-job-text-llm", json={"text": text}, headers=_auth("p7-cache-user"))
    assert r1.status_code == r2.status_code == 200, (r1.status_code, r2.status_code)
    assert r1.json() == r2.json()
    assert calls["n"] == 1, "an identical JD must not be billed twice"


def test_failed_extraction_is_not_cached(monkeypatch) -> None:
    text = f"Flaky posting {uuid.uuid4()}."

    def boom(**kwargs):
        raise LLMError("transient provider failure")

    monkeypatch.setattr(extraction, "structured_completion", boom)
    r1 = client.post("/utils/parse-job-text-llm", json={"text": text}, headers=_auth("p7-retry-user"))
    assert r1.status_code == 502

    monkeypatch.setattr(extraction, "structured_completion", lambda **kw: {"job title": "X"})
    r2 = client.post("/utils/parse-job-text-llm", json={"text": text}, headers=_auth("p7-retry-user"))
    assert r2.status_code == 200, "a failure must not poison the cache"


if __name__ == "__main__":
    raise SystemExit(_bootstrap.run_as_script(globals(), "Phase 7 cost-control"))
