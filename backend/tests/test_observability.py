"""Phase 4 o11y checks: PII redaction + content-free LLM traces.

    python tests/test_observability.py    (or: python -m pytest)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bootstrap  # noqa: E402
from app.observability.redaction import redact  # noqa: E402


def test_redacts_emails_and_phones() -> None:
    text = "Reach me at anwar.k@example.com or +1 (415) 555-0132."
    out = redact(text)
    assert "anwar.k@example.com" not in out and "[email]" in out
    assert "555-0132" not in out and "[phone]" in out


def test_keeps_resume_date_ranges() -> None:
    # 8 digits with a dash is a tenure range, not a phone number.
    assert redact("Backend Engineer, 2019 - 2023") == "Backend Engineer, 2019 - 2023"


def test_redacts_known_names_case_insensitively() -> None:
    out = redact("Interviewer: Thanks ANWAR. Candidate: I'm Anwar Khan.", names=["Anwar", "Khan"])
    assert "anwar" not in out.lower() and "khan" not in out.lower()
    assert "[name]" in out


def test_llm_trace_logs_metadata_not_content(monkeypatch) -> None:
    """The llm_trace line must carry latency/tokens, never prompt text."""
    import logging

    from app.llm import client as llm_client

    records: list[str] = []

    class _Handler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record.getMessage())

    class _FakeCompletion:
        class usage:
            prompt_tokens = 42
            completion_tokens = 7

        choices = [type("C", (), {"message": type("M", (), {"content": '{"ok": true}'})()})()]

    class _FakeClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    return _FakeCompletion()

    monkeypatch.setattr(llm_client, "get_cerebras_client", lambda: _FakeClient())
    handler = _Handler()
    trace_logger = logging.getLogger("app.llm.client")
    trace_logger.addHandler(handler)
    trace_logger.setLevel(logging.INFO)  # unconfigured root would filter INFO
    try:
        llm_client.structured_completion(
            messages=[{"role": "user", "content": "SECRET RESUME TEXT"}],
            schema={"type": "object"},
            schema_name="test_schema",
        )
    finally:
        trace_logger.removeHandler(handler)
        trace_logger.setLevel(logging.NOTSET)

    traces = [r for r in records if r.startswith("llm_trace")]
    assert traces, f"no llm_trace emitted; got {records}"
    assert "prompt_tokens=42" in traces[0] and "call=test_schema" in traces[0]
    assert "SECRET RESUME TEXT" not in " ".join(records), "prompt content must never be logged"


if __name__ == "__main__":
    raise SystemExit(_bootstrap.run_as_script(globals(), "observability"))
