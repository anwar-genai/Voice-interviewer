"""Observability: configured once here, instrumented inline at the call sites.

``metrics`` is deliberately not re-exported — it imports LiveKit, and the API
process has no reason to pull that in. The agent worker imports it directly.
"""

from .logging import configure_logging

__all__ = ["configure_logging"]
