"""Per-user rate limiting for paid endpoints (parse, token, feedback).

``rate_limit`` depends on ``require_user``, so a route that uses it is both
authenticated and throttled. The limit is per authenticated user, not per IP,
so one user can't burn another's quota.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException

from .auth import require_user
from .config import get_settings

_WINDOW_SECONDS = 60.0

# ponytail: in-process fixed window per user. Fine for one worker; swap the dict
# for Redis when the API runs multiple workers/instances (Phase 6).
_hits: dict[str, deque[float]] = defaultdict(deque)


def rate_limit(user_id: str = Depends(require_user)) -> str:
    """Allow up to ``rate_limit_per_minute`` requests per user per minute."""
    limit = get_settings().rate_limit_per_minute
    now = time.monotonic()
    hits = _hits[user_id]

    while hits and now - hits[0] > _WINDOW_SECONDS:
        hits.popleft()

    if len(hits) >= limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded, try again shortly")

    hits.append(now)
    return user_id
