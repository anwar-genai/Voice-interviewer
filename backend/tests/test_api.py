"""Phase 4 API tests: the HTTP layer against a mocked LLM (no Cerebras, no network).

Providers are patched at the one choke point (``structured_completion``), so these
exercise routing, auth, ownership, error translation, and persistence — everything
except the model itself.

    python tests/test_api.py        (or: python -m pytest)
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bootstrap  # noqa: E402

_bootstrap.bootstrap()  # env + throwaway DB, BEFORE importing the app

import jwt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.llm.extraction as extraction  # noqa: E402
import app.llm.feedback as llm_feedback  # noqa: E402
from app.db.models import Feedback, Interview, Turn  # noqa: E402
from app.db.session import session_scope  # noqa: E402
from app.llm.errors import LLMError  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)

FEEDBACK_JSON = {
    "strengths": ["Clear STAR structure in the deploy story"],
    "improvements": ["Quantify the impact of the fixes"],
    "recommendations": ["Practice a system-design walkthrough"],
    "overall_score": 8,
    "technical_score": 7,
    "communication_score": 9,
}


def _auth(sub: str) -> dict[str, str]:
    token = jwt.encode(
        {"sub": sub, "aud": "authenticated", "exp": int(time.time()) + 3600},
        _bootstrap.TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _seed_interview(user_id: str, *, candidate_text: str) -> str:
    with session_scope() as db:
        iv = Interview(
            user_id=user_id,
            room=f"room-{uuid.uuid4()}",
            status="completed",
            job={"job_title": "Backend Engineer"},
            resume="Backend engineer, 4 years of Python.",
        )
        iv.turns = [
            Turn(role="agent", content="Tell me about yourself."),
            Turn(role="user", content=candidate_text),
        ]
        db.add(iv)
        db.flush()
        return iv.id


SUBSTANTIVE = (
    "I am a backend engineer with four years of Python experience. I built a "
    "payments API on FastAPI and PostgreSQL, added idempotency keys, and was "
    "on call for a three-service platform with alerting on latency."
)


# --- /utils extraction -------------------------------------------------------

def test_parse_job_text_maps_llm_fields(monkeypatch) -> None:
    seen: dict = {}

    def fake_completion(**kwargs):
        seen.update(kwargs)
        return {"job title": "Backend Engineer", "job type": "full-time", "location": "Remote"}

    monkeypatch.setattr(extraction, "structured_completion", fake_completion)
    r = client.post(
        "/utils/parse-job-text-llm",
        json={"text": "Backend Engineer, full-time, remote."},
        headers=_auth("api-parse-user"),
    )
    assert r.status_code == 200, (r.status_code, r.text)
    body = r.json()
    assert body["job_title"] == "Backend Engineer" and body["job_type"] == "full-time"
    # The posting must reach the model inside its delimited untrusted block.
    assert "Backend Engineer, full-time, remote." in seen["messages"][1]["content"]


def test_parse_job_llm_failure_is_generic_502(monkeypatch) -> None:
    def boom(**kwargs):
        raise LLMError("provider stack trace with internal details")

    monkeypatch.setattr(extraction, "structured_completion", boom)
    r = client.post(
        "/utils/parse-job-text-llm",
        json={"text": "some posting"},
        headers=_auth("api-parse-err-user"),
    )
    assert r.status_code == 502, (r.status_code, r.text)
    assert "internal details" not in r.text, "provider errors must not leak to clients"


# --- /feedback ---------------------------------------------------------------

def test_feedback_scores_once_and_is_idempotent(monkeypatch) -> None:
    calls = {"n": 0}

    def fake_completion(**kwargs):
        calls["n"] += 1
        return dict(FEEDBACK_JSON)

    monkeypatch.setattr(llm_feedback, "structured_completion", fake_completion)
    iv_id = _seed_interview("api-fb-user", candidate_text=SUBSTANTIVE)
    headers = _auth("api-fb-user")

    r1 = client.post("/feedback/generate", json={"interview_id": iv_id}, headers=headers)
    assert r1.status_code == 200, (r1.status_code, r1.text)
    assert r1.json()["overall_score"] == 8

    r2 = client.post("/feedback/generate", json={"interview_id": iv_id}, headers=headers)
    assert r2.status_code == 200 and r2.json() == r1.json()
    assert calls["n"] == 1, "a second generate call must not re-bill the LLM"

    r3 = client.get(f"/feedback/{iv_id}", headers=headers)
    assert r3.status_code == 200 and r3.json() == r1.json()


def test_feedback_is_owner_scoped(monkeypatch) -> None:
    monkeypatch.setattr(llm_feedback, "structured_completion", lambda **kw: dict(FEEDBACK_JSON))
    iv_id = _seed_interview("api-owner-user", candidate_text=SUBSTANTIVE)

    r = client.post("/feedback/generate", json={"interview_id": iv_id}, headers=_auth("api-intruder"))
    assert r.status_code == 404, "another user's interview must look nonexistent"


def test_feedback_rejects_thin_transcript() -> None:
    iv_id = _seed_interview("api-thin-user", candidate_text="Um, not sure.")
    r = client.post("/feedback/generate", json={"interview_id": iv_id}, headers=_auth("api-thin-user"))
    assert r.status_code == 400, (r.status_code, r.text)


def test_feedback_llm_error_is_generic_502(monkeypatch) -> None:
    def boom(**kwargs):
        raise LLMError("secret internals")

    monkeypatch.setattr(llm_feedback, "structured_completion", boom)
    iv_id = _seed_interview("api-fb-err-user", candidate_text=SUBSTANTIVE)
    r = client.post("/feedback/generate", json={"interview_id": iv_id}, headers=_auth("api-fb-err-user"))
    assert r.status_code == 502, (r.status_code, r.text)
    assert "secret internals" not in r.text


def _score(iv_id: str) -> None:
    with session_scope() as db:
        db.add(Feedback(interview_id=iv_id, **FEEDBACK_JSON))


def test_share_mint_public_read_revoke() -> None:
    headers = _auth("api-share-user")
    iv_id = _seed_interview("api-share-user", candidate_text=SUBSTANTIVE)
    _score(iv_id)

    token = client.post(f"/interviews/{iv_id}/share", headers=headers).json()["token"]
    again = client.post(f"/interviews/{iv_id}/share", headers=headers).json()["token"]
    assert token == again, "sharing twice must reuse the same token"

    # Public read: no auth header, feedback only — no transcript/resume fields.
    r = client.get(f"/share/{token}")
    assert r.status_code == 200, (r.status_code, r.text)
    body = r.json()
    assert body["feedback"]["overall_score"] == FEEDBACK_JSON["overall_score"]
    assert body["job_title"] == "Backend Engineer"
    assert "resume" not in body and "turns" not in body

    client.delete(f"/interviews/{iv_id}/share", headers=headers)
    assert client.get(f"/share/{token}").status_code == 404, "revoked link must die"


def test_share_requires_score_and_ownership() -> None:
    iv_id = _seed_interview("api-share-owner", candidate_text=SUBSTANTIVE)
    r = client.post(f"/interviews/{iv_id}/share", headers=_auth("api-share-owner"))
    assert r.status_code == 400, "unscored interviews have nothing to share"

    _score(iv_id)
    r = client.post(f"/interviews/{iv_id}/share", headers=_auth("api-share-intruder"))
    assert r.status_code == 404, "another user's interview must look nonexistent"


if __name__ == "__main__":
    raise SystemExit(_bootstrap.run_as_script(globals(), "API"))
