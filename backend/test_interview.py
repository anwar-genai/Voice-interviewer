#!/usr/bin/env python
"""Test interview locally without LiveKit Cloud."""
import os
import sys
from pathlib import Path
import asyncio

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

# Test imports
try:
    from livekit import agents
    from livekit.agents import JobContext, WorkerOptions
    print("✅ LiveKit agents imported successfully")
except ImportError as e:
    print(f"❌ Failed to import LiveKit agents: {e}")
    print("Run: pip install livekit-agents[openai,silero,deepgram,turn-detector]")
    sys.exit(1)

try:
    from cerebras.cloud.sdk import Cerebras
    print("✅ Cerebras SDK imported successfully")
except ImportError as e:
    print(f"❌ Failed to import Cerebras: {e}")
    print("Run: pip install cerebras-cloud-sdk")
    sys.exit(1)

# Test API keys
api_key = os.getenv("CEREBRAS_API_KEY")
if api_key:
    print("✅ Cerebras API key found")
    # Test Cerebras connection
    try:
        client = Cerebras(api_key=api_key)
        completion = client.chat.completions.create(
            model="llama3.3-70b",
            messages=[{"role": "user", "content": "Say 'test ok' in 2 words"}],
            max_tokens=10
        )
        print(f"✅ Cerebras test: {completion.choices[0].message.content}")
    except Exception as e:
        print(f"❌ Cerebras API test failed: {e}")
else:
    print("❌ CEREBRAS_API_KEY not set")

deepgram_key = os.getenv("DEEPGRAM_API_KEY")
if deepgram_key:
    print("✅ Deepgram API key found")
else:
    print("❌ DEEPGRAM_API_KEY not set")

livekit_key = os.getenv("LIVEKIT_API_KEY") or os.getenv("LiveKit_API_KEY")
livekit_secret = os.getenv("LIVEKIT_API_SECRET") or os.getenv("LiveKit_API_SECRET")
livekit_url = os.getenv("LIVEKIT_URL") or os.getenv("LiveKit_URL")

if all([livekit_key, livekit_secret, livekit_url]):
    print("✅ LiveKit credentials found")
    print(f"   URL: {livekit_url}")
else:
    print("❌ LiveKit credentials missing")

print("\n" + "="*50)
print("If all checks pass, run the agent with:")
print("  python backend/run_agent.py dev")
print("\nThen in the frontend, click 'Start Mock Interview'")
print("="*50)
