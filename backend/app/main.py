import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .deps import include_routers
from .observability import configure_logging

logger = logging.getLogger("interview.api")


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    if not settings.auth_enabled:
        logger.warning("AUTH_ENABLED is false — every request runs as the dev user. Do not use in production.")

    app = FastAPI(title="Voice Interviewer API", version="0.1.0")

    # Bearer tokens, not cookies, so credentials stay off — which also means a
    # stray "*" in the allowlist can never be paired with credentials.
    origins = [o for o in settings.cors_origin_list if o != "*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    include_routers(app)

    return app


app = create_app()
