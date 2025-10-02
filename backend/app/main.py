from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .deps import include_routers
from dotenv import load_dotenv
import os


def create_app() -> FastAPI:
    # Load .env if present
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
    app = FastAPI(title="Voice Interviewer API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # tighten in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    include_routers(app)

    return app


app = create_app()


