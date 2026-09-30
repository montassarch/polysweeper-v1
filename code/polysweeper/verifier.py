"""Decide whether we may trust that a match is really over and who won."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Sequence, Tuple

from .models import NORMAL, SourceResult


@dataclass(frozen=True)
class Verification:
    ok: bool
    winner: Optional[str]
    finished_at: Optional[datetime]
    reasons: Tuple[str, ...]


def _norm(name: Optional[str]) -> str:
    return (name or "").strip().lower()


def verify(
    sources: Sequence[SourceResult],
    now: datetime,
    min_sources: int,
    confirm_minutes: int,
    max_data_age_minutes: int,
) -> Verification:
    """Strict: EVERY source must say finished + normal + same winner, be fresh,
    and the match must have ended at least `confirm_minutes` ago."""
    reasons = []

    names = {s.source for s in sources}
    if len(names) < min_sources:
        reasons.append(f"need {min_sources} independent sources, have {len(names)}")

    winners = set()
    finish_times = []
    for s in sources:
        if s.status != "finished":
            reasons.append(f"{s.source}: status is '{s.status}', not finished")
            continue
        if s.result_type != NORMAL:
            reasons.append(f"{s.source}: result type '{s.result_type}' may resolve 50/50")
            continue
        if not _norm(s.winner):
            reasons.append(f"{s.source}: finished but no winner given")
            continue
        if now - s.fetched_at > timedelta(minutes=max_data_age_minutes):
            reasons.append(f"{s.source}: data is stale")
            continue
        if s.finished_at is None:
            reasons.append(f"{s.source}: no finish time")
            continue
        winners.add(_norm(s.winner))
        finish_times.append(s.finished_at)

    if len(winners) > 1:
        reasons.append("sources disagree on the winner")

    last_finish = max(finish_times) if finish_times else None
    if last_finish is not None and now - last_finish < timedelta(minutes=confirm_minutes):
        reasons.append(f"only {int((now - last_finish).total_seconds() // 60)} min since the end; waiting {confirm_minutes}")

    if reasons:
        return Verification(False, None, last_finish, tuple(reasons))
    winner = next(iter(winners))
    return Verification(True, winner, last_finish, ())
