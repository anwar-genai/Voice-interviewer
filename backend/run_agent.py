#!/usr/bin/env python
"""
Standalone interview agent worker that connects to LiveKit Cloud.

Run separately from the FastAPI server:
    python run_agent.py dev

Uses livekit-agents 1.x. With no `agent_name` set on WorkerOptions the worker
uses *automatic dispatch*: it joins every room created in the LiveKit project,
so when the frontend connects to an `interview-*` room this agent auto-joins it.
The STT -> LLM -> TTS turn loop is driven automatically by the framework once
`session.start()` is called; there is no manual listen/speak loop in 1.x.
"""
import os
import sys
import json
import logging
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from backend/.env
load_dotenv(Path(__file__).parent / ".env")

# Ensure `app` package is importable when run from anywhere
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("interview-agent")

from livekit import agents
from livekit.agents import Agent, AgentSession, ChatContext, JobContext, WorkerOptions
from livekit.plugins import deepgram, openai, silero


def build_instructions(job_context: dict, candidate_context: str) -> str:
    """System prompt that drives the whole interview via automatic turn-taking."""
    job_title = job_context.get("job_title") or job_context.get("title") or "the role"
    return (
        "You are a professional, friendly AI interviewer conducting a spoken mock "
        f"job interview for {job_title}. Speak naturally and concisely — this is a "
        "voice conversation, so keep each turn to one or two sentences and never use "
        "markdown, lists, or emojis.\n\n"
        "Conduct the interview in phases: (1) a brief warm welcome and 'tell me about "
        "yourself', (2) technical questions relevant to the role, (3) one or two "
        "behavioral questions using the STAR method, (4) a short wrap-up inviting the "
        "candidate to ask questions. Ask ONE question at a time, then wait for the "
        "candidate to answer before continuing. Ask natural follow-ups based on what "
        "they say. Do not answer the questions for them.\n\n"
        f"Job details: {json.dumps(job_context)}\n"
        f"Candidate resume: {candidate_context}"
    )


async def entrypoint(ctx: JobContext):
    """Called automatically for each room the worker is dispatched to."""
    logger.info("Agent dispatched to room: %s", ctx.room.name)
    await ctx.connect()
    logger.info("Connected to room")

    # Pull job/resume context from room metadata if the frontend provided it.
    job_context: dict = {}
    candidate_context = ""
    if ctx.room.metadata:
        try:
            metadata = json.loads(ctx.room.metadata)
            job_context = metadata.get("job", {}) or {}
            candidate_context = metadata.get("resume", "") or ""
            logger.info(
                "Loaded metadata: job=%s resume=%s",
                bool(job_context),
                bool(candidate_context),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to parse room metadata: %s", exc)

    if not job_context:
        job_context = {"job_title": "Software Engineer", "qualifications": "Python experience"}
    if not candidate_context:
        candidate_context = "Experienced software engineer with Python and web development skills."

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-2", api_key=os.getenv("DEEPGRAM_API_KEY")),
        llm=openai.LLM.with_cerebras(
            model=os.getenv("CEREBRAS_MODEL", "gpt-oss-120b"),
            temperature=float(os.getenv("AGENT_TEMPERATURE", "0.7")),
            api_key=os.getenv("CEREBRAS_API_KEY"),
        ),
        tts=deepgram.TTS(
            model=os.getenv("DEEPGRAM_TTS_MODEL", "aura-asteria-en"),
            api_key=os.getenv("DEEPGRAM_API_KEY"),
        ),
    )

    agent = Agent(
        instructions=build_instructions(job_context, candidate_context),
        chat_ctx=ChatContext(),
    )

    logger.info("Starting agent session...")
    await session.start(agent=agent, room=ctx.room)

    # Kick off the interview. generate_reply() speaks the result automatically;
    # after this the framework handles every subsequent user turn on its own.
    logger.info("Generating opening greeting...")
    await session.generate_reply(
        instructions=(
            "Warmly greet the candidate, briefly say you'll run a short mock "
            "interview, and ask them to tell you a little about themselves. "
            "Keep it to one or two sentences."
        )
    )


if __name__ == "__main__":
    api_key = os.getenv("LIVEKIT_API_KEY") or os.getenv("LiveKit_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET") or os.getenv("LiveKit_API_SECRET")
    ws_url = os.getenv("LIVEKIT_URL") or os.getenv("LiveKit_URL")

    if not all([api_key, api_secret, ws_url]):
        logger.error("Missing LiveKit credentials! Check your .env file.")
        sys.exit(1)

    # Make sure the SDK sees the canonical env var names it reads internally.
    os.environ.setdefault("LIVEKIT_API_KEY", api_key)
    os.environ.setdefault("LIVEKIT_API_SECRET", api_secret)
    os.environ.setdefault("LIVEKIT_URL", ws_url)

    logger.info("Starting agent worker...")
    logger.info("LiveKit URL: %s", ws_url)

    # No agent_name => automatic dispatch: the worker joins every new room.
    agents.cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
