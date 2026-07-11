"""Typed, validated application settings — the single source of configuration.

Everything (API, agent worker, evals) reads config from here rather than calling
``os.getenv`` inline. Values come from the environment, falling back to
``backend/.env`` for local development.

Secrets are read from the environment, never hard-coded, so moving from a local
``.env`` to an injected platform vault needs no code change.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BACKEND_DIR / ".env"


class MissingConfigError(RuntimeError):
    """A required setting is absent. Raised at use site, not import time."""


class Settings(BaseSettings):
    """All configuration for the API and the agent worker.

    Provider credentials are optional so the API can boot (and `/health` can
    answer) without them; the code paths that need a credential call the
    matching ``require_*`` accessor and fail with a clear message.
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LiveKit -----------------------------------------------------------
    livekit_url: str | None = None
    livekit_api_key: str | None = None
    livekit_api_secret: str | None = None

    # How long a participant join token stays valid.
    join_token_ttl_seconds: int = 3600
    # Room lifetime after the last participant leaves.
    room_empty_timeout_seconds: int = 300

    # --- Cerebras (LLM) ----------------------------------------------------
    cerebras_api_key: str | None = None
    cerebras_model: str = "gpt-oss-120b"

    # --- Deepgram (STT/TTS) ------------------------------------------------
    deepgram_api_key: str | None = None
    deepgram_stt_model: str = "nova-2"
    deepgram_tts_model: str = "aura-asteria-en"

    # --- Agent behaviour ---------------------------------------------------
    agent_temperature: float = 0.7

    # --- API ---------------------------------------------------------------
    # Comma-separated in the environment: "http://localhost:5173,https://app.example.com"
    # Phase 1 replaces the "*" default with a real allowlist.
    cors_origins: str = "*"
    log_level: str = "INFO"

    # --- Cost telemetry ----------------------------------------------------
    # Provider list prices, overridable per environment. Used only to attach a
    # cost estimate to each interview's usage summary; they are estimates, not
    # billing figures.
    cerebras_input_usd_per_mtok: float = 0.25
    cerebras_output_usd_per_mtok: float = 0.69
    deepgram_stt_usd_per_minute: float = 0.0077
    deepgram_tts_usd_per_1k_chars: float = 0.030

    # --- Job-description fetching ------------------------------------------
    fetch_timeout_seconds: int = 20
    fetch_user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
        )
    )

    @field_validator("log_level")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def require_livekit(self) -> tuple[str, str, str]:
        """Return ``(url, api_key, api_secret)`` or raise."""
        missing = [
            name
            for name, value in (
                ("LIVEKIT_URL", self.livekit_url),
                ("LIVEKIT_API_KEY", self.livekit_api_key),
                ("LIVEKIT_API_SECRET", self.livekit_api_secret),
            )
            if not value
        ]
        if missing:
            raise MissingConfigError(f"LiveKit is not configured: missing {', '.join(missing)}")
        return self.livekit_url, self.livekit_api_key, self.livekit_api_secret  # type: ignore[return-value]

    def require_cerebras_api_key(self) -> str:
        if not self.cerebras_api_key:
            raise MissingConfigError("Cerebras is not configured: missing CEREBRAS_API_KEY")
        return self.cerebras_api_key

    def require_deepgram_api_key(self) -> str:
        if not self.deepgram_api_key:
            raise MissingConfigError("Deepgram is not configured: missing DEEPGRAM_API_KEY")
        return self.deepgram_api_key


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
