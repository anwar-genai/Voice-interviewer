#!/usr/bin/env python
"""Manual smoke test: can we reach the providers? Phase 4 converts this to pytest."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import MissingConfigError, get_settings
from app.llm import LLMError, extract_job


def main() -> int:
    settings = get_settings()

    try:
        from livekit import agents  # noqa: F401

        print("OK   livekit-agents imported")
    except ImportError as exc:
        print(f"FAIL livekit-agents: {exc}")
        return 1

    try:
        job = extract_job("Senior Python Engineer, full-time, remote. Requires 5 years of Django.")
        print(f"OK   Cerebras extraction: title={job.job_title!r} type={job.job_type!r}")
    except (LLMError, MissingConfigError) as exc:
        print(f"FAIL Cerebras extraction: {exc}")
        return 1

    print(f"{'OK  ' if settings.deepgram_api_key else 'MISS'} DEEPGRAM_API_KEY")
    print(f"{'OK  ' if settings.livekit_url else 'MISS'} LIVEKIT_URL")

    print("\nStart the agent with:  python run_agent.py dev")
    print("Then click 'Start Mock Interview' in the frontend.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
