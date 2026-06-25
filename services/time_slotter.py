"""Pure time-slot assignment functions."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Sequence

import pandas as pd

from rules.weekly_rules import (
    EXTERNAL_DRIVE_MWF_DAY_SLOTS,
    EXTERNAL_DRIVE_SLOTS,
    TOLERANCE_MINUTES,
    WEARABLE_SLOTS,
    SlotRule,
)


def slots_for_date(kind: str, broadcast_date: date) -> tuple[SlotRule, ...]:
    """Return configured slots for a date and weekly file type."""
    if kind == "wearable":
        return WEARABLE_SLOTS
    if kind != "external":
        raise ValueError("위클리 파일 유형은 external 또는 wearable이어야 합니다.")
    if broadcast_date.weekday() not in (0, 2, 4):
        return EXTERNAL_DRIVE_SLOTS
    retained = tuple(slot for slot in EXTERNAL_DRIVE_SLOTS if slot.label not in {"11:50", "14:00"})
    insert_at = next(index for index, slot in enumerate(retained) if slot.label == "16:10")
    return retained[:insert_at] + EXTERNAL_DRIVE_MWF_DAY_SLOTS + retained[insert_at:]


def slot_bounds(broadcast_date: date, slot: SlotRule) -> tuple[datetime, datetime]:
    start = datetime.combine(broadcast_date, slot.start)
    end_date = broadcast_date + timedelta(days=1) if slot.end <= slot.start else broadcast_date
    return start, datetime.combine(end_date, slot.end)


def _distance_to_interval(moment: datetime, start: datetime, end: datetime) -> float:
    if start <= moment < end:
        return 0.0
    return min(abs((moment - start).total_seconds()), abs((moment - end).total_seconds()))


def assign_slot(
    value: object,
    kind: str,
    candidate_date: date | None = None,
    slots: Sequence[SlotRule] | None = None,
) -> tuple[date, str] | None:
    """Assign one payment timestamp to one nearest eligible slot."""
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    moment = parsed.to_pydatetime()
    dates = [candidate_date] if candidate_date else [moment.date(), moment.date() - timedelta(days=1)]
    candidates: list[tuple[float, float, date, str]] = []
    tolerance = timedelta(minutes=TOLERANCE_MINUTES)
    for broadcast_date in dates:
        current_slots = tuple(slots) if slots is not None else slots_for_date(kind, broadcast_date)
        for slot in current_slots:
            start, end = slot_bounds(broadcast_date, slot)
            if start - tolerance <= moment <= end + tolerance:
                distance = _distance_to_interval(moment, start, end)
                candidates.append((distance, -start.timestamp(), broadcast_date, slot.label))
    if not candidates:
        return None
    _, _, broadcast_date, label = min(candidates)
    return broadcast_date, label


def inferred_broadcast_date(value: object, last_end: time = time(1, 18)) -> date | None:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    moment = parsed.to_pydatetime()
    return moment.date() - timedelta(days=1) if moment.time() <= last_end else moment.date()

