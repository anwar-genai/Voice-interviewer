#!/usr/bin/env python
"""The interview agent worker. Connects to LiveKit and runs the voice session.

Run separately from the FastAPI server:
    python run_agent.py dev

Uses livekit-agents 1.x. With no `agent_name` set on WorkerOptions the worker
uses *automatic dispatch*: it joins every room created in the LiveKit project,
so when the frontend connects to an `interview-*` room this agent auto-joins it.
The STT -> LLM -> TTS turn loop is driven automatically by the framework once
`session.start()` is called; there is no manual listen/speak loop in 1.x.

This file is transport only. What the interviewer is *told* lives in `app/llm/`.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Ensure `app` package is importable when run from anywhere.
sys.path.insert(0, str(Path(__file__).parent))

from livekit import agents
from livekit.agents import Agent, AgentSession, ChatContext, JobContext, WorkerOptions
from livekit.plugins import deepgram, openai, silero
from livekit.plugins.turn_detector.english import EnglishModel
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from app.core.config import MissingConfigError, Settings, get_settings
from app.db.transcript import attach_transcript_capture
from app.llm import build_instructions, parse_room_metadata, technical_keywords
from app.llm.prompts import INTERVIEWER_GREETING_INSTRUCTIONS
from app.observability import configure_logging
from app.observability.metrics import attach_session_metrics

logger = logging.getLogger("interview.agent")


def _turn_detection(settings: Settings):
    """Pick the end-of-utterance detector. Semantic models decide when the user
    has actually finished a thought instead of waiting out a fixed silence.

    The "english"/"multilingual" models need their files fetched once:
        python run_agent.py download-files
    """
    choice = settings.turn_detection_model.lower()
    if choice == "english":
        return EnglishModel()
    if choice == "multilingual":
        return MultilingualModel()
    return choice  # "vad" / "stt": silence- or STT-based endpointing only


async def entrypoint(ctx: JobContext) -> None:
    """Called automatically for each room the worker is dispatched to."""
    settings = get_settings()
    logger.info("Agent dispatched to room: %s", ctx.room.name)

    await ctx.connect()
    logger.info("Connected to room")

    context = parse_room_metadata(ctx.room.metadata)
    logger.info(
        "Interview context: job=%s resume_chars=%d",
        context.job.get("job_title", "unknown"),
        len(context.resume),
    )

    # STT vocabulary hints from this interview's JD/resume, so Deepgram doesn't
    # mangle niche terms ("PyPDF2" -> "pie PDF") and unfairly tank the feedback.
    vocab = technical_keywords(context)
    stt_kwargs: dict = {}
    if vocab:
        if "nova-3" in settings.deepgram_stt_model:
            stt_kwargs["keyterms"] = vocab
        else:  # nova-2 family takes (word, boost) pairs
            stt_kwargs["keywords"] = [(w, 1.5) for w in vocab]
        logger.info("STT vocabulary: %d term(s), e.g. %s", len(vocab), vocab[:5])

    session = AgentSession(
        # Semantic turn detection so the agent replies as soon as you've finished
        # a thought, instead of waiting out the full silence timeout.
        turn_detection=_turn_detection(settings),
        min_endpointing_delay=settings.min_endpointing_delay_seconds,
        max_endpointing_delay=settings.max_endpointing_delay_seconds,
        # Noise robustness: how long "speech" must last to count as a barge-in.
        min_interruption_duration=settings.min_interruption_duration_seconds,
        vad=silero.VAD.load(activation_threshold=settings.vad_activation_threshold),
        stt=deepgram.STT(
            model=settings.deepgram_stt_model,
            api_key=settings.require_deepgram_api_key(),
            **stt_kwargs,
        ),
        llm=openai.LLM.with_cerebras(
            model=settings.cerebras_model,
            temperature=settings.agent_temperature,
            api_key=settings.require_cerebras_api_key(),
        ),
        tts=deepgram.TTS(
            model=settings.deepgram_tts_model,
            api_key=settings.require_deepgram_api_key(),
        ),
    )

    # Per-turn latency now; a usage + cost summary when the session ends.
    attach_session_metrics(session, ctx, room_name=ctx.room.name)

    # Persist each turn + the interview's lifecycle status (created -> in_progress
    # -> completed/dropped) so it survives the session and can be scored.
    attach_transcript_capture(session, room_name=ctx.room.name)

    agent = Agent(
        instructions=build_instructions(context),
        chat_ctx=ChatContext(),
    )

    logger.info("Starting agent session...")
    await session.start(agent=agent, room=ctx.room)

    # Kick off the interview. generate_reply() speaks the result automatically;
    # after this the framework handles every subsequent user turn on its own.
    logger.info("Generating opening greeting...")
    await session.generate_reply(instructions=INTERVIEWER_GREETING_INSTRUCTIONS)


def main() -> None:
    configure_logging()
    settings = get_settings()

    try:
        livekit_url, api_key, api_secret = settings.require_livekit()
        settings.require_cerebras_api_key()
        settings.require_deepgram_api_key()
    except MissingConfigError as exc:
        logger.error("%s. Check backend/.env against env.example.", exc)
        sys.exit(1)

    # `agents.cli.run_app` reads these from the process environment, not from us.
    os.environ.setdefault("LIVEKIT_URL", livekit_url)
    os.environ.setdefault("LIVEKIT_API_KEY", api_key)
    os.environ.setdefault("LIVEKIT_API_SECRET", api_secret)

    logger.info("Starting agent worker against %s", livekit_url)

    # No agent_name => automatic dispatch: the worker joins every new room.
    agents.cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))


if __name__ == "__main__":
    main()
