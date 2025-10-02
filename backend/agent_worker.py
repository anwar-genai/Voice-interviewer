import os
from dotenv import load_dotenv


def main() -> None:
    # Load env from backend/.env if present
    here = os.path.dirname(__file__)
    load_dotenv(os.path.join(here, ".env"))

    try:
        from livekit import agents
        from app.agents.interviewer import entrypoint
    except Exception as exc:  # pragma: no cover
        raise SystemExit(f"Missing livekit-agents or agent code not importable: {exc}")

    # Start a local worker that connects to LiveKit Cloud. The agent uses
    # our interviewer entrypoint. If you want to pass resume/job context,
    # adapt entrypoint to fetch them from room metadata or an API.
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))


if __name__ == "__main__":
    main()


