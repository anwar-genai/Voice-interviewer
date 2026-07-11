"""Retention: delete interviews (and their turns + feedback) past the TTL.

Data minimization — we don't keep interview data forever. A scheduler runs this
periodically (Phase 6); until then it's a manual/cron entry point:

    python -m app.db.retention
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..observability import configure_logging
from .models import Interview
from .session import _session_factory

logger = logging.getLogger("interview.retention")


def purge_expired_interviews(db: Session, older_than_days: int) -> int:
    """Delete interviews older than the cutoff; returns how many were removed."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    expired = db.scalars(select(Interview).where(Interview.created_at < cutoff)).all()
    for iv in expired:  # ponytail: ORM cascade delete; bulk delete + DB cascade if volume grows
        db.delete(iv)
    db.commit()
    return len(expired)


# A worker crash never fires the session close event, stranding interviews as
# in_progress forever. Anything in_progress this long is over.
STALE_IN_PROGRESS_HOURS = 6


def mark_stale_in_progress(db: Session, *, older_than_hours: int = STALE_IN_PROGRESS_HOURS) -> int:
    """Mark interviews stuck in_progress as dropped; returns how many."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
    result = db.execute(
        update(Interview)
        .where(Interview.status == "in_progress", Interview.updated_at < cutoff)
        .values(status="dropped")
    )
    db.commit()
    return result.rowcount


def main() -> None:
    configure_logging()
    days = get_settings().retention_days
    db = _session_factory()()
    try:
        stale = mark_stale_in_progress(db)
        removed = purge_expired_interviews(db, days)
        logger.info(
            "Retention: marked %d stale interview(s) dropped, removed %d older than %d days",
            stale,
            removed,
            days,
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
