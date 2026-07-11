"""Errors raised by the LLM core.

Transport translates these: `InvalidInputError` is the caller's fault (4xx),
`LLMError` is the provider's (5xx).
"""

from __future__ import annotations


class InvalidInputError(ValueError):
    """The caller supplied input the LLM core will not act on."""


class LLMError(RuntimeError):
    """The LLM call failed, or returned something we could not parse."""
