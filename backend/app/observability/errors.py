"""Error reporting: Sentry when SENTRY_DSN is configured, silent no-op otherwise.

Sentry's logging integration is on by default, so every ``logger.error`` /
``logger.exception`` already in the codebase (LLM failures, provider errors from
the voice session) becomes an alerting event with no further instrumentation.
"""

from __future__ import annotations

import logging

from ..core.config import get_settings

logger = logging.getLogger(__name__)


def init_error_reporting(component: str) -> None:
    """Call once at process start (API and agent worker each pass their name)."""
    dsn = get_settings().sentry_dsn
    if not dsn:
        return
    try:
        import sentry_sdk
    except ImportError:
        logger.warning("SENTRY_DSN is set but sentry-sdk is not installed")
        return

    # send_default_pii stays False: no request bodies, no user identifiers —
    # transcripts/resumes must never reach the error tracker.
    sentry_sdk.init(dsn=dsn, send_default_pii=False)
    sentry_sdk.set_tag("component", component)
    logger.info("Sentry error reporting enabled (component=%s)", component)
