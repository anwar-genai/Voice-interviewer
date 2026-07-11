"""Golden-set eval for job extraction (`app.llm.extraction.extract_job`).

Scoring is deliberately lenient on free-text fields: the model may phrase
`qualifications` any number of ways, so we assert that an expected keyword
appears. `job_type` is drawn from a closed enum, so it is matched exactly.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.llm import extract_job
from app.llm.prompts import EXTRACTION_PROMPT_VERSION

from ..harness import CaseResult, FieldResult, SuiteResult

DATASET = Path(__file__).resolve().parent.parent / "datasets" / "extraction_golden.json"
THRESHOLD = 0.8

# Fields matched exactly rather than by keyword containment.
EXACT_FIELDS = {"job_type"}


def _matches(field_name: str, expected: str, actual: str | None) -> bool:
    if actual is None:
        return False
    if field_name in EXACT_FIELDS:
        return actual.strip().lower() == expected.strip().lower()
    return expected.strip().lower() in actual.lower()


def run() -> SuiteResult:
    cases = json.loads(DATASET.read_text(encoding="utf-8"))
    result = SuiteResult(name=f"extraction ({EXTRACTION_PROMPT_VERSION})", threshold=THRESHOLD)

    for case in cases:
        case_result = CaseResult(case_id=case["id"])
        try:
            parsed = extract_job(case["posting"])
        except Exception as exc:  # noqa: BLE001 - an eval records failures, never raises
            case_result.error = str(exc)
            result.cases.append(case_result)
            continue

        for field_name, expected in case["expected"].items():
            actual = getattr(parsed, field_name, None)
            case_result.fields.append(
                FieldResult(
                    field_name=field_name,
                    expected=expected,
                    actual=actual,
                    passed=_matches(field_name, expected, actual),
                )
            )
        result.cases.append(case_result)

    return result
