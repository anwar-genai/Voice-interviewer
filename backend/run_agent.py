#!/usr/bin/env python
"""
Standalone agent runner that connects to LiveKit Cloud.
Run this separately from your FastAPI server:
    python backend/run_agent.py dev
"""
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent / ".env")

# Now import LiveKit and run
from livekit import agents
from livekit.agents import JobContext, WorkerOptions
from app.agents.interviewer import Assistant, entrypoint as original_entrypoint
from datetime import datetime
from livekit.agents import ChatContext, AgentSession
from livekit.plugins import deepgram, openai, silero
import json


async def interview_entrypoint(ctx: JobContext):
    """Modified entrypoint that reads job/resume from room metadata."""
    
    await ctx.connect()
    
    # Get room metadata if available (you'd pass this when creating the room)
    room_metadata = ctx.room.metadata
    job_context = {}
    candidate_context = ""
    
    if room_metadata:
        try:
            metadata = json.loads(room_metadata)
            job_context = metadata.get("job", {})
            candidate_context = metadata.get("resume", "")
        except:
            pass
    
    # If no metadata, use defaults
    if not job_context:
        job_context = {"job_title": "Software Engineer", "qualifications": "Python experience"}
    if not candidate_context:
        candidate_context = "Experienced software engineer with Python and web development skills."
    
    # Create session with Cerebras LLM
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-2"),
        llm=openai.LLM.with_cerebras(
            model=os.getenv("CEREBRAS_MODEL", "llama3.3-70b"),
            temperature=float(os.getenv("AGENT_TEMPERATURE", "0.7")),
        ),
        tts=deepgram.TTS(model=os.getenv("DEEPGRAM_TTS_MODEL", "aura-asteria-en")),
    )
    
    # Set up context
    today = datetime.now().strftime("%B %d, %Y")
    chat_ctx = ChatContext()
    chat_ctx.add_message(role="user", content=f"I am interviewing for this job: {job_context}.")
    chat_ctx.add_message(role="user", content=f"This is my resume: {candidate_context}.")
    chat_ctx.add_message(
        role="assistant", 
        content=f"Today's date is {today}. Don't repeat this to the user. This is only for your reference."
    )
    
    # Create assistant
    assistant = Assistant(chat_ctx=chat_ctx)
    
    # Start session
    await session.start(agent=assistant, room=ctx.room)
    
    # Generate initial greeting
    initial_msg = await session.generate_reply(
        instructions="Greet the candidate warmly and ask them to tell you about themselves to start the interview. Be professional but friendly."
    )
    chat_ctx.add_message(role="assistant", content=initial_msg)
    await session.speak(initial_msg)
    
    # Main conversation loop
    while True:
        user_input = await session.listen()
        if user_input:
            chat_ctx.add_message(role="user", content=user_input)
            
            # Generate contextual interview response
            response = await session.generate_reply(
                instructions=(
                    "You are conducting a professional job interview. "
                    "Ask relevant follow-up questions based on their answers. "
                    "Focus on their experience, skills, and fit for the role. "
                    "Keep responses concise and natural."
                )
            )
            
            chat_ctx.add_message(role="assistant", content=response)
            await session.speak(response)


if __name__ == "__main__":
    # Run the agent worker
    agents.cli.run_app(
        WorkerOptions(
            entrypoint_fnc=interview_entrypoint,
            api_key=os.getenv("LIVEKIT_API_KEY") or os.getenv("LiveKit_API_KEY"),
            api_secret=os.getenv("LIVEKIT_API_SECRET") or os.getenv("LiveKit_API_SECRET"),
            ws_url=os.getenv("LIVEKIT_URL") or os.getenv("LiveKit_URL"),
        )
    )
