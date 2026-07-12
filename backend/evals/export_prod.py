"""Export completed prod interviews into an eval dataset (the prod→eval loop).

Reads the configured ``DATABASE_URL``, redacts PII (emails, phones, the
candidate's name from the resume's first line), and writes
``datasets/prod_transcripts.json`` — real-world cases to grow the feedback and
calibration suites from.

    python -m evals.export_prod [limit]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import select

from app.db.models import Interview
from app.db.session import session_scope
from app.llm.guardrails import candidate_names
from app.observability.redaction import redact
from app.routers.feedback import build_transcript

OUT = Path(__file__).resolve().parent / "datasets" / "prod_transcripts.json"


def export(limit: int = 50) -> int:
    cases = []
    with session_scope() as db:
        interviews = db.scalars(
            select(Interview)
            .where(Interview.status == "completed")
            .order_by(Interview.created_at.desc())
            .limit(limit)
        ).all()
        for iv in interviews:
            transcript, candidate_text = build_transcript(iv.turns)
            if not candidate_text.strip():
                continue
            names = candidate_names(iv.resume)
            cases.append(
                {
                    "id": iv.id,  # a UUID, not PII
                    "job": {"job_title": (iv.job or {}).get("job_title")},
                    "transcript": redact(transcript, names=names),
                    "overall_score": iv.feedback.overall_score if iv.feedback else None,
                }
            )

    OUT.write_text(json.dumps(cases, indent=2), encoding="utf-8")
    print(f"Exported {len(cases)} interview(s) -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(export(int(sys.argv[1])) if len(sys.argv) > 1 else export())
