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

    # --- Database ----------------------------------------------------------
    # Supabase Postgres connection string. Use the direct connection or the
    # session-mode pooler (transaction-mode pooler breaks Alembic DDL).
    # e.g. postgresql+psycopg://postgres:<pw>@db.<ref>.supabase.co:5432/postgres
    database_url: str | None = None
    # Data minimization: interviews older than this are purged (app/db/retention.py).
    retention_days: int = 30

    # --- Auth (Supabase) ---------------------------------------------------
    # The backend verifies Supabase-issued JWTs; Supabase owns the user store.
    # New projects sign tokens with asymmetric keys (ES256/RS256) verified via
    # the project's JWKS endpoint -> needs supabase_url. Older projects sign
    # HS256 with the shared secret -> needs supabase_jwt_secret. Either works.
    supabase_url: str | None = None
    supabase_jwt_secret: str | None = None
    # Fail closed. Set false ONLY for local dev / tests with no Supabase project;
    # a warning is logged at startup when it is off.
    auth_enabled: bool = True

    # --- Request limits (also bound untrusted input into prompts) ----------
    max_pdf_bytes: int = 10 * 1024 * 1024  # 10 MB
    max_job_text_chars: int = 50_000
    max_resume_chars: int = 50_000

    # --- Rate limiting (in-process; see app/core/ratelimit.py) -------------
    rate_limit_per_minute: int = 20

    # --- Cost controls (Phase 7; enforced in /agent/join-token + the worker) --
    # Interviews a user may start per UTC day. DB-backed (unlike the rate
    # limiter), so it survives restarts and holds across machines.
    daily_interview_limit: int = 10
    # The agent wraps up and ends the session after this long. 0 disables.
    max_interview_minutes: int = 30
    # Global cap on simultaneously active interviews — bounds total provider
    # spend and protects worker capacity.
    max_concurrent_interviews: int = 10
    # Session cap for anonymous (no-signup demo) users; guests also get 1
    # interview per day instead of daily_interview_limit.
    demo_interview_minutes: int = 5

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

    # --- Turn detection / endpointing (voice turn-taking responsiveness) ----
    # Semantic end-of-utterance model: "english" (fast, EN-only), "multilingual",
    # or "vad"/"stt" to fall back to silence/STT endpointing only.
    turn_detection_model: str = "english"
    # How long to wait after you stop speaking before the agent replies. The
    # semantic model picks within this range: min when it's confident you're
    # done, up to max when you still sound mid-thought. Tune to mic/speaking pace.
    min_endpointing_delay_seconds: float = 0.5
    max_endpointing_delay_seconds: float = 4.0
    # Noise robustness. Raise both in a noisy room (fan, street) so background
    # sound doesn't read as speech and interrupt the agent mid-sentence:
    # activation_threshold ~0.6-0.7 makes the VAD less trigger-happy;
    # min_interruption_duration ~1.0 requires sustained speech to barge in.
    # (False interruptions already auto-resume after ~2s via LiveKit defaults.)
    vad_activation_threshold: float = 0.5
    min_interruption_duration_seconds: float = 0.5

    # --- Evals ---------------------------------------------------------------
    # Judge for LLM-judge evals: a different model family from the one being
    # judged, so the grader doesn't share the graded model's blind spots.
    # ponytail: same provider (one API key, zero new accounts); point this at a
    # stronger external judge via env when an account for one exists.
    eval_judge_model: str = "zai-glm-4.7"

    # --- Error tracking ------------------------------------------------------
    # Set to a Sentry DSN to report errors from the API and the agent worker
    # (that's what makes provider errors page someone). Off when unset.
    sentry_dsn: str | None = None

    # --- Metrics export -------------------------------------------------------
    # When set, the agent worker serves Prometheus metrics on :{port}/metrics
    # (scraped by the platform, e.g. Fly.io -> fly-metrics.net Grafana). Off when unset.
    prometheus_port: int | None = None

    # --- API ---------------------------------------------------------------
    # Comma-separated in the environment: "http://localhost:5173,https://app.example.com".
    # Explicit allowlist, never "*" — the API is authenticated and CORS is enforced.
    cors_origins: str = "http://localhost:5173"
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

    def require_database_url(self) -> str:
        if not self.database_url:
            raise MissingConfigError("Database is not configured: missing DATABASE_URL")
        return self.database_url

    def require_supabase_jwt_secret(self) -> str:
        if not self.supabase_jwt_secret:
            raise MissingConfigError("Token is HS256 but SUPABASE_JWT_SECRET is not set")
        return self.supabase_jwt_secret

    def require_supabase_url(self) -> str:
        if not self.supabase_url:
            raise MissingConfigError("Token uses signing keys but SUPABASE_URL is not set")
        return self.supabase_url

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
