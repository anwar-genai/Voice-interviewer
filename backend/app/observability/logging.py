"""Logging configuration. Configure once, at process start."""

from __future__ import annotations

import logging

from ..core.config import get_settings

_configured = False


def configure_logging() -> None:
    """Set up root logging from settings. Safe to call more than once."""
    global _configured
    if _configured:
        return

    logging.basicConfig(
        level=get_settings().log_level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    _configured = True
