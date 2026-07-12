"""The LLM judge: a *different* model family from the one being judged
(``EVAL_JUDGE_MODEL``, default llama-3.3-70b vs the app's gpt-oss-120b), so the
grader doesn't share the graded model's blind spots. Deterministic (temp 0).
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.llm.client import structured_completion


def judge_completion(
    *, messages: list[dict[str, str]], schema: dict[str, Any], schema_name: str
) -> dict[str, Any]:
    return structured_completion(
        messages=messages,
        schema=schema,
        schema_name=schema_name,
        model=get_settings().eval_judge_model,
        temperature=0.0,
    )
