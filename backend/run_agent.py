#!/usr/bin/env python
"""
Standalone agent runner that connects to LiveKit Cloud.
Run this separately from your FastAPI server:
    python backend/run_agent.py dev
"""
import os
import sys
import logging
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent / ".env")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Now import LiveKit and run
from livekit import agents
from livekit.agents import JobContext, WorkerOptions, JobRequest
from app.agents.interviewer import Assistant
from datetime import datetime
from livekit.agents import ChatContext, AgentSession
from livekit.plugins import deepgram, openai, silero
import json


async def interview_entrypoint(ctx: JobContext):
    """Interview agent entrypoint."""
    logger.info(f"Agent joining room: {ctx.room.name}")
    
    try:
        await ctx.connect()
        logger.info("Connected to room")
        
        # Get room metadata if available
        room_metadata = ctx.room.metadata
        job_context = {}
        candidate_context = ""
        
        if room_metadata:
            try:
                metadata = json.loads(room_metadata)
                job_context = metadata.get("job", {})
                candidate_context = metadata.get("resume", "")
                logger.info(f"Loaded metadata: job={bool(job_context)}, resume={bool(candidate_context)}")
            except Exception as e:
                logger.warning(f"Failed to parse metadata: {e}")
        
        # If no metadata, use defaults
        if not job_context:
            job_context = {"job_title": "Software Engineer", "qualifications": "Python experience"}
        if not candidate_context:
            candidate_context = "Experienced software engineer with Python and web development skills."
        
        logger.info("Creating agent session...")
        
        # Create session with Cerebras LLM
        session = AgentSession(
            vad=silero.VAD.load(),
            stt=deepgram.STT(model="nova-2"),
            llm=openai.LLM.with_cerebras(
                model=os.getenv("CEREBRAS_MODEL", "llama3.3-70b"),
                temperature=float(os.getenv("AGENT_TEMPERATURE", "0.7")),
                api_key=os.getenv("CEREBRAS_API_KEY"),
            ),
            tts=deepgram.TTS(
                model=os.getenv("DEEPGRAM_TTS_MODEL", "aura-asteria-en"),
                api_key=os.getenv("DEEPGRAM_API_KEY"),
            ),
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
        
        # Create assistant with proper instructions
        assistant = Assistant(chat_ctx=chat_ctx)
        
        logger.info("Starting agent session...")
        
        # Start session
        await session.start(agent=assistant, room=ctx.room)
        
        logger.info("Generating initial greeting...")
        
        # Generate initial greeting
        initial_msg = await session.generate_reply(
            instructions="Greet the candidate warmly and ask them to tell you about themselves to start the interview. Be professional but friendly. Keep it brief."
        )
        
        if initial_msg:
            chat_ctx.add_message(role="assistant", content=initial_msg)
            await session.speak(initial_msg)
            logger.info("Spoke initial greeting")
        
        # Main conversation loop
        logger.info("Entering main conversation loop...")
        while ctx.room.connection_state == "connected":
            user_input = await session.listen()
            if user_input:
                logger.info(f"User said: {user_input[:50]}...")
                chat_ctx.add_message(role="user", content=user_input)
                
                # Generate contextual interview response
                response = await session.generate_reply(
                    instructions=(
                        "You are conducting a professional job interview. "
                        "Ask relevant follow-up questions based on their answers. "
                        "Focus on their experience, skills, and fit for the role. "
                        "Keep responses concise and natural. One or two sentences max."
                    )
                )
                
                if response:
                    chat_ctx.add_message(role="assistant", content=response)
                    await session.speak(response)
                    logger.info(f"Agent responded: {response[:50]}...")
                    
    except Exception as e:
        logger.error(f"Error in agent: {e}", exc_info=True)
        raise


async def request_handler(request: JobRequest) -> None:
    """Handle job requests - accept all interview rooms."""
    logger.info(f"Received job request for room: {request.room.name}")
    # Accept all rooms that start with "interview-"
    if request.room.name.startswith("interview-"):
        await request.accept(interview_entrypoint)
        logger.info(f"Accepted job for room: {request.room.name}")
    else:
        await request.reject()
        logger.info(f"Rejected job for room: {request.room.name}")


if __name__ == "__main__":
    # Check credentials
    api_key = os.getenv("LIVEKIT_API_KEY") or os.getenv("LiveKit_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET") or os.getenv("LiveKit_API_SECRET")
    ws_url = os.getenv("LIVEKIT_URL") or os.getenv("LiveKit_URL")
    
    if not all([api_key, api_secret, ws_url]):
        logger.error("Missing LiveKit credentials! Check your .env file")
        sys.exit(1)
    
    logger.info(f"Starting agent worker...")
    logger.info(f"LiveKit URL: {ws_url}")
    
    # Run the agent worker with request handler
    agents.cli.run_app(
        WorkerOptions(
            request_handler=request_handler,
            api_key=api_key,
            api_secret=api_secret,
            ws_url=ws_url,
        )
    )