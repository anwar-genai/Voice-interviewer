"""Cerebras client and the one place a structured LLM call is made.

Keeping every completion behind ``structured_completion`` means the guardrail
layer (Phase 1/3) and prompt tracing (Phase 4) wrap a single function instead of
call sites scattered across routers.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

from ..core.config import get_settings
from .errors import LLMError

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_cerebras_client() -> Any:
    """Return a shared Cerebras client. Imported lazily: the SDK is optional."""
    try:
        from cerebras.cloud.sdk import Cerebras
    except ImportError as exc:  # pragma: no cover - depends on install extras
        raise LLMError(f"Cerebras SDK not available: {exc}") from exc

    return Cerebras(api_key=get_settings().require_cerebras_api_key())


def structured_completion(
    *,
    messages: list[dict[str, str]],
    schema: dict[str, Any],
    schema_name: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """Run a chat completion constrained to ``schema`` and return the parsed object."""
    settings = get_settings()
    client = get_cerebras_client()

    try:
        completion = client.chat.completions.create(
            model=settings.cerebras_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
            },
        )
    except Exception as exc:  # noqa: BLE001 - provider SDK raises many types
        raise LLMError(f"LLM request failed: {exc}") from exc

    try:
        content = completion.choices[0].message.content
        return json.loads(content)
    except (AttributeError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise LLMError(f"Could not parse LLM output: {exc}") from exc
