"""Pure time-slot assignment functions."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Sequence

import pandas as pd

from rules.weekly_rules import (
    DISABLED_SESSIONS,
    EXTERNAL_DRIVE_SLOTS,
    TOLERANCE_MINUTES,
    VALID_SESSIONS_ONLY,
    WEARABLE_DATE_OVERRIDES,
    WEARABLE_SLOTS,
    SlotRule,
)


CustomSlots = dict[date, tuple[SlotRule, ...]]


def slots_for_date(kind: str, broadcast_date: date, custom_slots: CustomSlots | None = None) -> tuple[SlotRule, ...]:
    """Return configured slots for a date and weekly file type."""
    if custom_slots and broadcast_date in custom_slots:
        return custom_slots[broadcast_date]
    if kind == "wearable":
        slots = WEARABLE_DATE_OVERRIDES.get(broadcast_date, WEARABLE_SLOTS)
    elif kind == "external":
        slots = EXTERNAL_DRIVE_SLOTS
    else:
        raise ValueError("위클리 파일 유형은 external 또는 wearable이어야 합니다.")
    valid = VALID_SESSIONS_ONLY.get((kind, broadcast_date))
    if valid is not None:
        slots = tuple(slot for slot in slots if slot.label in valid)
    return slots


def slot_bounds(broadcast_date: date, slot: SlotRule) -> tuple[datetime, datetime]:
    start = datetime.combine(broadcast_date, slot.start)
    end_date = broadcast_date + timedelta(days=1) if slot.end <= slot.start else broadcast_date
    return start, datetime.combine(end_date, slot.end)


def effective_slot_bounds(broadcast_date: date, slot: SlotRule) -> tuple[datetime, datetime]:
    start_time = slot.effective_start or slot.start
    end_time = slot.effective_end or slot.end
    start = datetime.combine(broadcast_date, start_time)
    end_date = broadcast_date + timedelta(days=1) if end_time <= start_time else broadcast_date
    return start, datetime.combine(end_date, end_time)


def session_is_disabled(kind: str, broadcast_date: date, label: str | None) -> bool:
    return bool(label and label in DISABLED_SESSIONS.get((kind, broadcast_date), set()))


def _distance_to_interval(moment: datetime, start: datetime, end: datetime) -> float:
    if start <= moment < end:
        return 0.0
    return min(abs((moment - start).total_seconds()), abs((moment - end).total_seconds()))


def assign_slot(
    value: object,
    kind: str,
    candidate_date: date | None = None,
    slots: Sequence[SlotRule] | None = None,
    custom_slots: CustomSlots | None = None,
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
        if custom_slots is not None and broadcast_date not in custom_slots:
            continue
        current_slots = tuple(slots) if slots is not None else slots_for_date(kind, broadcast_date, custom_slots)
        for slot in current_slots:
            start, end = slot_bounds(broadcast_date, slot)
            effective_start, effective_end = effective_slot_bounds(broadcast_date, slot)
            if slot.effective_start is None and slot.effective_end is None:
                effective_start -= tolerance
                effective_end += tolerance
            if effective_start <= moment <= effective_end:
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
