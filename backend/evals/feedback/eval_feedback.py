"""Feedback evals: groundedness + calibration (`app.llm.feedback`).

Two things we can measure now that feedback is wired and transcripts exist:

- **Groundedness** — the guard must refuse a transcript with too little candidate
  speech (that is where hallucinated strengths come from). Deterministic, no LLM.
- **Calibration** — scoring the *same* transcript several times should land close
  together. We measure the spread of ``overall_score`` across runs.

Phase 4 adds a stronger, different judge model for semantic groundedness; this
suite is the honest floor available at Phase 3.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.llm import InvalidInputError, generate_feedback, require_groundable_transcript
from app.llm.prompts import FEEDBACK_PROMPT_VERSION

from ..harness import CaseResult, FieldResult, SuiteResult

DATASET = Path(__file__).resolve().parent.parent / "datasets" / "feedback_transcripts.json"
THRESHOLD = 1.0  # every check must pass

CALIBRATION_RUNS = 3
CALIBRATION_MAX_SPREAD = 3  # max acceptable (max-min) of overall_score across runs


def _groundedness_case(thin: dict) -> CaseResult:
    """The guard must reject a transcript the candidate barely spoke in."""
    case = CaseResult(case_id="groundedness_guard_rejects_thin_transcript")
    try:
        require_groundable_transcript(thin["candidate_text"])
        raised = False
    except InvalidInputError:
        raised = True
    case.fields.append(
        FieldResult(field_name="rejects_thin_transcript", expected="raises",
                    actual="raised" if raised else "did-not-raise", passed=raised)
    )
    return case


def _calibration_case(sample: dict) -> CaseResult:
    """The same transcript scored N times should land within a small spread."""
    case = CaseResult(case_id="calibration_overall_score_spread")
    try:
        scores = [
            generate_feedback(
                job=sample["job"], resume=sample["resume"], transcript=sample["transcript"]
            ).overall_score
            for _ in range(CALIBRATION_RUNS)
        ]
    except Exception as exc:  # noqa: BLE001 - an eval records failures, never raises
        case.error = str(exc)
        return case

    spread = max(scores) - min(scores)
    case.fields.append(
        FieldResult(
            field_name="overall_score_spread",
            expected=f"<={CALIBRATION_MAX_SPREAD} (scores {scores})",
            actual=str(spread),
            passed=spread <= CALIBRATION_MAX_SPREAD,
        )
    )
    return case


def run() -> SuiteResult:
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    result = SuiteResult(name=f"feedback ({FEEDBACK_PROMPT_VERSION})", threshold=THRESHOLD)
    result.cases.append(_groundedness_case(data["thin"]))
    result.cases.append(_calibration_case(data["substantive"]))
    return result
