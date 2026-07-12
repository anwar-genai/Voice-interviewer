"""Pytest entry: set env + throwaway DB before any test module imports app.*."""

import _bootstrap

_bootstrap.bootstrap()
