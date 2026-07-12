"""STT-fairness checks: keyword mining for Deepgram + the transcript-aware rubric.

    python tests/test_stt_fairness.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bootstrap  # noqa: E402
from app.llm import technical_keywords  # noqa: E402
from app.llm.prompts import FEEDBACK_PROMPT_VERSION, FEEDBACK_RUBRIC  # noqa: E402
from app.llm.schemas import InterviewContext  # noqa: E402


def test_mines_technical_terms_from_resume_and_job() -> None:
    ctx = InterviewContext(
        job={"job_title": "Backend Engineer", "qualifications": "FastAPI, PostgreSQL, GDPR compliance"},
        resume="EXPERIENCE\nBuilt pipelines with PyPDF2, LangChain and C++; deployed on S3.",
    )
    got = {k.lower() for k in technical_keywords(ctx)}
    for term in ("pypdf2", "langchain", "c++", "s3", "fastapi", "postgresql", "gdpr"):
        assert term in got, f"missing {term!r} in {sorted(got)}"


def test_skips_plain_words_and_shouting_headers() -> None:
    ctx = InterviewContext(job={}, resume="summary\nEXPERIENCE working with teams and building software daily.")
    got = technical_keywords(ctx)
    assert got == [], f"plain prose should yield nothing, got {got}"


def test_two_letter_acronyms_dropped_but_digit_shorts_kept() -> None:
    # "AI" boosted at 1.5x hijacked "Hi" in a live interview; digit shorts stay.
    ctx = InterviewContext(job={"qualifications": "AI, ML, S3, RAG, LLM"}, resume="skills first")
    got = {k.lower() for k in technical_keywords(ctx)}
    assert "ai" not in got and "ml" not in got, got
    assert {"s3", "rag", "llm"} <= got, got


def test_candidate_name_from_resume_first_line() -> None:
    ctx = InterviewContext(job={}, resume="Anwar Khan\nSenior engineer working with software.")
    got = {k.lower() for k in technical_keywords(ctx)}
    assert {"anwar", "khan"} <= got, got


def test_dedupes_and_caps() -> None:
    ctx = InterviewContext(job={}, resume="FastAPI fastapi FASTAPI " + " ".join(f"Tool{i}X" for i in range(100)))
    got = technical_keywords(ctx, limit=10)
    assert len(got) == 10, len(got)
    assert sum(1 for k in got if k.lower() == "fastapi") == 1, "case-insensitive dedupe"


def test_rubric_is_transcription_aware() -> None:
    assert "speech-recognition" in FEEDBACK_RUBRIC
    assert FEEDBACK_PROMPT_VERSION != "feedback-v1", "prompt text changed; version must bump"


def test_feedback_scoring_is_name_blind(monkeypatch) -> None:
    """The scorer must never see the candidate's name — a gender/ethnicity
    proxy that evals/fairness showed can move scores."""
    import app.llm.feedback as fb

    seen: dict = {}

    def fake_completion(**kwargs):
        seen.update(kwargs)
        return {
            "strengths": [], "improvements": [], "recommendations": [],
            "overall_score": 5, "technical_score": 5, "communication_score": 5,
        }

    monkeypatch.setattr(fb, "structured_completion", fake_completion)
    fb.generate_feedback(
        job={"job_title": "Backend Engineer"},
        resume="Ayesha Khan\nEngineer with Python. Contact: ayesha.k@example.com",
        transcript="Interviewer: Welcome, Ayesha. Candidate: I'm Ayesha Khan and I build payments APIs.",
    )
    prompt = seen["messages"][1]["content"]
    assert "Ayesha" not in prompt and "Khan" not in prompt, "candidate name leaked into the scoring prompt"
    assert "ayesha.k@example.com" not in prompt, "contact PII leaked into the scoring prompt"
    assert "payments APIs" in prompt, "substance must survive redaction"


if __name__ == "__main__":
    raise SystemExit(_bootstrap.run_as_script(globals(), "STT-fairness"))
