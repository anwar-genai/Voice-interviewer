"""Voice-pipeline telemetry: per-turn latency and per-interview cost.

Wraps LiveKit's ``MetricsCollectedEvent`` (emitted after every STT/LLM/TTS/EOU
step) and ``UsageCollector`` (which accumulates tokens, characters, and audio
seconds for the whole session).

This module imports LiveKit, so only the agent worker imports it — not the API.
"""

from __future__ import annotations

import logging
from typing import Any

from livekit.agents import AgentSession, JobContext, MetricsCollectedEvent, metrics

from ..core.config import get_settings

logger = logging.getLogger("interview.metrics")


def estimate_cost_usd(summary: metrics.UsageSummary) -> dict[str, float]:
    """Estimate what one interview cost, broken down by provider.

    Rates come from settings and are list prices, not billing data. Cached
    prompt tokens are billed here at the full input rate — an overestimate.
    """
    settings = get_settings()

    llm_usd = (
        summary.llm_prompt_tokens / 1_000_000 * settings.cerebras_input_usd_per_mtok
        + summary.llm_completion_tokens / 1_000_000 * settings.cerebras_output_usd_per_mtok
    )
    stt_usd = summary.stt_audio_duration / 60 * settings.deepgram_stt_usd_per_minute
    tts_usd = summary.tts_characters_count / 1_000 * settings.deepgram_tts_usd_per_1k_chars

    return {
        "llm_usd": round(llm_usd, 6),
        "stt_usd": round(stt_usd, 6),
        "tts_usd": round(tts_usd, 6),
        "total_usd": round(llm_usd + stt_usd + tts_usd, 6),
    }


def _latency_fields(m: Any) -> dict[str, float] | None:
    """Pull the latency number that matters out of whichever metric this is."""
    if isinstance(m, metrics.LLMMetrics):
        return {"llm_ttft_s": m.ttft, "llm_tokens_per_second": m.tokens_per_second}
    if isinstance(m, metrics.TTSMetrics):
        return {"tts_ttfb_s": m.ttfb}
    if isinstance(m, metrics.EOUMetrics):
        return {
            "eou_delay_s": m.end_of_utterance_delay,
            "transcription_delay_s": m.transcription_delay,
        }
    return None


def attach_error_events(session: AgentSession, *, room_name: str) -> None:
    """Log a structured ``provider_error`` event for every STT/LLM/TTS failure.

    ERROR level means Sentry (when configured) turns each one into an alerting
    event — that is the "provider errors page someone" wire.
    """

    @session.on("error")
    def _on_error(ev: Any) -> None:
        err = getattr(ev, "error", ev)
        source = getattr(ev, "source", None)
        logger.error(
            "provider_error room=%s source=%s recoverable=%s error=%s",
            room_name,
            type(source).__name__ if source is not None else "unknown",
            getattr(err, "recoverable", None),
            err,
        )


def attach_session_metrics(
    session: AgentSession, ctx: JobContext, *, room_name: str
) -> metrics.UsageCollector:
    """Log per-turn latency, and a usage + cost summary when the session ends.

    Returns the collector so callers can read the summary themselves.
    """
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent) -> None:
        usage_collector.collect(ev.metrics)

        latency = _latency_fields(ev.metrics)
        if latency is not None:
            logger.info(
                "turn_latency room=%s %s",
                room_name,
                " ".join(f"{k}={v:.3f}" for k, v in latency.items() if v is not None),
            )

    async def _log_usage_summary() -> None:
        summary = usage_collector.get_summary()
        cost = estimate_cost_usd(summary)
        logger.info(
            "interview_usage room=%s llm_prompt_tokens=%d llm_completion_tokens=%d "
            "tts_characters=%d stt_audio_s=%.1f cost_usd=%.6f (llm=%.6f stt=%.6f tts=%.6f)",
            room_name,
            summary.llm_prompt_tokens,
            summary.llm_completion_tokens,
            summary.tts_characters_count,
            summary.stt_audio_duration,
            cost["total_usd"],
            cost["llm_usd"],
            cost["stt_usd"],
            cost["tts_usd"],
        )

    ctx.add_shutdown_callback(_log_usage_summary)
    return usage_collector
