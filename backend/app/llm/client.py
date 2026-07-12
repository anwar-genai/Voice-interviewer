"""Cerebras client and the one place a structured LLM call is made.

Keeping every completion behind ``structured_completion`` means the guardrail
layer (Phase 1/3) and prompt tracing (Phase 4) wrap a single function instead of
call sites scattered across routers.
"""

from __future__ import annotations

import json
import logging
import time
from functools import lru_cache
from typing import Any

from ..core.config import get_settings
from ..observability.tracing import current_interview_id
from .errors import LLMError

logger = logging.getLogger(__name__)


def _trace(call: str, model: str, started: float, completion: Any) -> None:
    """One llm_trace line per completion: metadata only, never content (PII)."""
    usage = getattr(completion, "usage", None)
    logger.info(
        "llm_trace call=%s model=%s latency_ms=%.0f prompt_tokens=%s "
        "completion_tokens=%s interview=%s",
        call,
        model,
        (time.perf_counter() - started) * 1000,
        getattr(usage, "prompt_tokens", None),
        getattr(usage, "completion_tokens", None),
        current_interview_id.get() or "-",
    )


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
    model: str | None = None,
) -> dict[str, Any]:
    """Run a chat completion constrained to ``schema`` and return the parsed object.

    ``model`` overrides the configured default — the eval harness uses it to run
    its judge on a different model family than the one being judged.
    """
    model = model or get_settings().cerebras_model
    client = get_cerebras_client()

    started = time.perf_counter()
    try:
        completion = client.chat.completions.create(
            model=model,
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
    _trace(schema_name, model, started, completion)

    try:
        content = completion.choices[0].message.content
        return json.loads(content)
    except (AttributeError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise LLMError(f"Could not parse LLM output: {exc}") from exc


def chat_completion(
    *,
    messages: list[dict[str, str]],
    temperature: float | None = None,
    max_tokens: int | None = None,
    model: str | None = None,
) -> str:
    """Plain-text completion. The eval harness uses this to replay the live
    interviewer's prompt, which in production runs inside LiveKit's plugin."""
    model = model or get_settings().cerebras_model
    client = get_cerebras_client()

    started = time.perf_counter()
    try:
        completion = client.chat.completions.create(
            model=model, messages=messages, temperature=temperature, max_tokens=max_tokens
        )
    except Exception as exc:  # noqa: BLE001 - provider SDK raises many types
        raise LLMError(f"LLM request failed: {exc}") from exc
    _trace("chat", model, started, completion)

    try:
        content = completion.choices[0].message.content
    except (AttributeError, IndexError) as exc:
        raise LLMError(f"Could not read LLM output: {exc}") from exc
    if not content:
        raise LLMError("LLM returned an empty completion")
    return content
