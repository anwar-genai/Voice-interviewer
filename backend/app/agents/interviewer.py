import os
from datetime import datetime
from typing import Any


# Lazy import heavy deps so the API can start without them installed locally
try:
    from livekit.agents import Agent, AgentSession, JobContext, ChatContext  # type: ignore[import-not-found]
    from livekit.plugins import deepgram, openai, silero  # type: ignore[import-not-found]
    from cerebras.cloud.sdk import Cerebras  # type: ignore[import-not-found]
except Exception:  # pragma: no cover
    Agent = object  # type: ignore
    AgentSession = object  # type: ignore
    JobContext = object  # type: ignore
    ChatContext = object  # type: ignore
    deepgram = None  # type: ignore
    openai = None  # type: ignore
    silero = None  # type: ignore
    Cerebras = None  # type: ignore


class Assistant(Agent):  # type: ignore[misc]
    def __init__(self, chat_ctx: "ChatContext") -> None:  # noqa: F821
        super().__init__(
            chat_ctx=chat_ctx,
            instructions=(
                "You are a voice assistant that helps the user practice for an interview."
            ),
        )


async def entrypoint(
    ctx: "JobContext",
    candidate_context: str = "",
    job_context: dict[str, Any] | None = None,
):  # noqa: F821
    if deepgram is None or openai is None or silero is None:
        raise RuntimeError("LiveKit plugins not available. Ensure dependencies are installed.")

    await ctx.connect()

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-3"),
        llm=openai.LLM.with_cerebras(
            model=os.getenv("CEREBRAS_MODEL", "llama3.3-70b"),
            temperature=float(os.getenv("AGENT_TEMPERATURE", "0.7")),
        ),
        tts=deepgram.TTS(model=os.getenv("DEEPGRAM_TTS_MODEL", "aura-2-thalia-en")),
    )

    today = datetime.now().strftime("%B %d, %Y")
    chat_ctx = ChatContext()
    jc = job_context or {}
    chat_ctx.add_message(role="user", content=f"I am interviewing for this job: {jc}.")
    chat_ctx.add_message(role="user", content=f"This is my resume: {candidate_context}.")
    chat_ctx.add_message(role="assistant", content=(
        f"Today's date is {today}. Don't repeat this to the user. This is only for your reference."
    ))

    await session.start(agent=Assistant(chat_ctx=chat_ctx), room=ctx.room)

    assistant_msg = await session.generate_reply(
        instructions=(
            "In one sentence tell the user you will conduct a mock interview, then pause."
        )
    )
    chat_ctx.add_message(role="assistant", content=assistant_msg)

    while True:
        user_input = await session.listen()
        if user_input:
            chat_ctx.add_message(role="user", content=user_input)
            feedback_msg = await session.generate_reply(
                instructions=(
                    "Give a short, informal sentence of feedback without repeating the user's response. Then, pause."
                )
            )
            chat_ctx.add_message(role="assistant", content=feedback_msg)
            await session.speak(feedback_msg)


