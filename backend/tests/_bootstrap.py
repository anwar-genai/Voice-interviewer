"""Shared test bootstrap: environment + throwaway SQLite DB.

Must run before anything imports ``app.*``. Both entry points call it —
pytest (via ``conftest.py``, which loads first) and the plain
``python tests/test_x.py`` scripts; whoever calls first wins, later calls no-op.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

TEST_JWT_SECRET = "test-jwt-secret"
# The auth probes hit real DB-backed routes, so the suite needs actual tables:
# a throwaway SQLite file works across the TestClient's threads where :memory:
# would not.
DB_PATH = Path(tempfile.gettempdir()) / "vi_test.db"

_done = False


def bootstrap() -> None:
    global _done
    if _done:
        return
    _done = True

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    DB_PATH.unlink(missing_ok=True)
    os.environ.update(
        AUTH_ENABLED="true",
        SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
        SUPABASE_URL="https://example.supabase.co",
        RATE_LIMIT_PER_MINUTE="3",
        DATABASE_URL=f"sqlite:///{DB_PATH.as_posix()}",
    )

    from app.core.config import get_settings

    get_settings.cache_clear()  # drop settings cached by a prior import

    import app.db.models  # noqa: F401 — register tables on the metadata
    from app.db import Base
    from app.db.session import _engine

    Base.metadata.create_all(_engine())


class MonkeyPatch:
    """Minimal pytest-monkeypatch stand-in for the plain-python entry points."""

    def __init__(self) -> None:
        self._undo: list = []

    def setattr(self, target, name, value) -> None:
        old = getattr(target, name)
        self._undo.append((target, name, old))
        setattr(target, name, value)

    def undo(self) -> None:
        for target, name, old in reversed(self._undo):
            setattr(target, name, old)


def run_as_script(module_globals: dict, label: str) -> int:
    """Run every ``test_*`` function in a module without pytest."""
    tests = [(k, v) for k, v in sorted(module_globals.items()) if k.startswith("test_") and callable(v)]
    for name, fn in tests:
        mp = MonkeyPatch()
        try:
            fn(mp) if fn.__code__.co_argcount else fn()
        finally:
            mp.undo()
        print(f"OK  {name}")
    print(f"\nAll {len(tests)} {label} checks passed.")
    return 0
