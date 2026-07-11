#!/usr/bin/env python
"""Manual check that credentials are configured. Phase 4 converts this to pytest."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import get_settings


def main() -> int:
    settings = get_settings()

    required = {
        "LIVEKIT_URL": settings.livekit_url,
        "LIVEKIT_API_KEY": settings.livekit_api_key,
        "LIVEKIT_API_SECRET": settings.livekit_api_secret,
        "CEREBRAS_API_KEY": settings.cerebras_api_key,
        "DEEPGRAM_API_KEY": settings.deepgram_api_key,
    }

    for name, value in required.items():
        print(f"{'OK  ' if value else 'MISS'} {name}")

    missing = [name for name, value in required.items() if not value]
    if missing:
        print(f"\nMissing {len(missing)} setting(s). Copy env.example to .env and fill them in.")
        return 1

    print(f"\nAll credentials set. LiveKit URL: {settings.livekit_url}")
    print(f"Models: cerebras={settings.cerebras_model} "
          f"stt={settings.deepgram_stt_model} tts={settings.deepgram_tts_model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
