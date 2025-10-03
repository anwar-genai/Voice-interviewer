#!/usr/bin/env python
"""
Improved agent runner with better audio and interview features.
"""
import os
import sys
import logging
import json
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from livekit import agents
from livekit.agents import JobContext, WorkerOptions, JobRequest
from app.agents.interviewer import Assistant
from livekit.agents import ChatContext, AgentSession
from livekit.plugins import deepgram, openai, silero
from livekit.agents.voice_assistant import VoiceAssistant


async def improved_interview_entrypoint(ctx: JobContext):
    """Enhanced interview agent with better audio and features."""
    logger.info(f"Agent joining room: {ctx.room.name}")
    
    try:
        await ctx.connect()
        logger.info("Connected to room")
        
        # Get room metadata
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
        
        # Use defaults if no metadata
        if not job_context:
            job_context = {
                "job_title": "Software Engineer", 
                "qualifications": "Python, web development experience",
                "responsibilities": "Develop and maintain web applications"
            }
        if not candidate_context:
            candidate_context = "Experienced software engineer with Python and web development skills."
        
        logger.info("Creating improved agent session...")
        
        # IMPROVED: Better audio configuration
        session = AgentSession(
            vad=silero.VAD.load(),
            # IMPROVED: Use faster STT model
            stt=deepgram.STT(
                model="nova-2-general",  # Faster than nova-2
                language="en",
                smart_format=True,
                punctuation=True,
            ),
            # IMPROVED: Better LLM configuration
            llm=openai.LLM.with_cerebras(
                model=os.getenv("CEREBRAS_MODEL", "llama3.3-70b"),
                temperature=0.8,  # Slightly more creative
                max_tokens=150,   # Keep responses concise
                api_key=os.getenv("CEREBRAS_API_KEY"),
            ),
            # IMPROVED: Faster TTS model
            tts=deepgram.TTS(
                model="aura-asteria-en",  # Faster than aura-2-thalia
                voice="asteria",
                speed=1.1,  # Slightly faster speech
                api_key=os.getenv("DEEPGRAM_API_KEY"),
            ),
        )
        
        # IMPROVED: Better interview context
        today = datetime.now().strftime("%B %d, %Y")
        chat_ctx = ChatContext()
        
        # More detailed context for better interviews
        interview_prompt = f"""
        You are conducting a professional job interview for the position of {job_context.get('job_title', 'Software Engineer')}.
        
        Job Requirements: {job_context.get('qualifications', 'Not specified')}
        Key Responsibilities: {job_context.get('responsibilities', 'Not specified')}
        
        Candidate Background: {candidate_context[:500]}...
        
        Today's date: {today}
        
        Interview Guidelines:
        1. Start with a warm greeting and introduction
        2. Ask about their background and experience
        3. Ask behavioral questions (STAR method)
        4. Ask technical questions relevant to the role
        5. Allow them to ask questions about the company/role
        6. Keep responses concise (1-2 sentences)
        7. Be encouraging and professional
        8. Take notes mentally on their responses
        """
        
        chat_ctx.add_message(role="system", content=interview_prompt)
        
        # Create assistant with improved instructions
        assistant = Assistant(chat_ctx=chat_ctx)
        
        logger.info("Starting improved agent session...")
        await session.start(agent=assistant, room=ctx.room)
        
        # IMPROVED: Better initial greeting
        initial_msg = await session.generate_reply(
            instructions="""
            Greet the candidate warmly and introduce yourself as their interviewer.
            Ask them to tell you about themselves and their background.
            Keep it conversational and welcoming. One sentence only.
            """
        )
        
        if initial_msg:
            chat_ctx.add_message(role="assistant", content=initial_msg)
            await session.speak(initial_msg)
            logger.info("Spoke initial greeting")
        
        # IMPROVED: Enhanced conversation loop with interview phases
        conversation_phase = "introduction"
        question_count = 0
        
        logger.info("Entering enhanced conversation loop...")
        
        while ctx.room.connection_state == "connected":
            user_input = await session.listen()
            if user_input:
                logger.info(f"User said: {user_input[:50]}...")
                chat_ctx.add_message(role="user", content=user_input)
                question_count += 1
                
                # IMPROVED: Context-aware responses based on interview phase
                if question_count <= 2:
                    # Introduction phase
                    instructions = """
                    Ask follow-up questions about their background, education, or previous experience.
                    Show interest in their journey. Keep responses encouraging and brief.
                    """
                elif question_count <= 5:
                    # Technical/experience phase
                    instructions = """
                    Ask about specific technical skills, projects, or achievements mentioned in their resume.
                    Use the STAR method (Situation, Task, Action, Result) for behavioral questions.
                    Keep responses concise and engaging.
                    """
                elif question_count <= 7:
                    # Deep dive phase
                    instructions = """
                    Ask about challenges they've faced, how they handle teamwork, or their career goals.
                    Show genuine interest in their problem-solving abilities.
                    Keep responses brief and encouraging.
                    """
                else:
                    # Wrap-up phase
                    instructions = """
                    Ask if they have any questions about the role or company.
                    Thank them for their time and provide next steps.
                    Keep responses brief and professional.
                    """
                
                response = await session.generate_reply(instructions=instructions)
                
                if response:
                    chat_ctx.add_message(role="assistant", content=response)
                    await session.speak(response)
                    logger.info(f"Agent responded: {response[:50]}...")
                    
    except Exception as e:
        logger.error(f"Error in agent: {e}", exc_info=True)
        raise


async def request_handler(request: JobRequest) -> None:
    """Handle job requests."""
    logger.info(f"Received job request for room: {request.room.name}")
    if request.room.name.startswith("interview-"):
        await request.accept(improved_interview_entrypoint)
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
    
    logger.info("Starting IMPROVED agent worker...")
    logger.info(f"LiveKit URL: {ws_url}")
    
    # Run the improved agent worker
    agents.cli.run_app(
        WorkerOptions(
            request_handler=request_handler,
            api_key=api_key,
            api_secret=api_secret,
            ws_url=ws_url,
        )
    )
