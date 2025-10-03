#!/usr/bin/env python
"""Test LiveKit connection and credentials."""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent / ".env")

def test_credentials():
    """Test if LiveKit credentials are properly set."""
    api_key = os.getenv("LIVEKIT_API_KEY") or os.getenv("LiveKit_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET") or os.getenv("LiveKit_API_SECRET")
    url = os.getenv("LIVEKIT_URL") or os.getenv("LiveKit_URL")
    
    print("🔍 Checking LiveKit credentials...")
    print(f"✅ API Key: {'Set' if api_key else '❌ Missing'}")
    print(f"✅ API Secret: {'Set' if api_secret else '❌ Missing'}")
    print(f"✅ URL: {url if url else '❌ Missing'}")
    
    if not all([api_key, api_secret, url]):
        print("\n❌ Missing credentials! Make sure backend/.env has:")
        print("LIVEKIT_API_KEY=<your-key>")
        print("LIVEKIT_API_SECRET=<your-secret>")
        print("LIVEKIT_URL=wss://<your-project>.livekit.cloud")
        return False
    
    print("\n🔍 Checking other API keys...")
    cerebras = os.getenv("CEREBRAS_API_KEY")
    deepgram = os.getenv("DEEPGRAM_API_KEY")
    
    print(f"✅ Cerebras: {'Set' if cerebras else '❌ Missing'}")
    print(f"✅ Deepgram: {'Set' if deepgram else '❌ Missing'}")
    
    if not all([cerebras, deepgram]):
        print("\n⚠️ Missing AI provider keys. Agent may not work properly.")
    
    print("\n✅ All critical credentials are set!")
    return True

if __name__ == "__main__":
    test_credentials()
