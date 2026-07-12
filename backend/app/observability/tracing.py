"""Correlation for LLM traces: which interview a completion belongs to.

The trace itself is the structured ``llm_trace`` log line emitted by
``app.llm.client`` — metadata only (model, latency, token counts), never prompt
or completion content, so no PII enters the o11y layer. Set the contextvar at
the point that knows the interview (the feedback router); everything the call
touches downstream inherits it.
"""

from __future__ import annotations

from contextvars import ContextVar

current_interview_id: ContextVar[str | None] = ContextVar("current_interview_id", default=None)
