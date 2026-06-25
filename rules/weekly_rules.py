"""Weekly time-slot configuration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time


@dataclass(frozen=True)
class SlotRule:
    label: str
    start: time
    end: time


WEARABLE_SLOTS = (
    SlotRule("1:10", time(1, 10), time(3, 10)),
    SlotRule("3:20", time(3, 20), time(5, 20)),
    SlotRule("5:30", time(5, 30), time(7, 30)),
    SlotRule("9:30", time(9, 30), time(11, 30)),
    SlotRule("11:40", time(11, 40), time(13, 40)),
    SlotRule("13:50", time(13, 50), time(15, 50)),
    SlotRule("16:00", time(16), time(18)),
    SlotRule("18:10", time(18, 10), time(20, 10)),
    SlotRule("20:20", time(20, 20), time(22, 20)),
    SlotRule("23:00", time(23), time(1)),
)

EXTERNAL_DRIVE_SLOTS = (
    SlotRule("1:20", time(1, 20), time(3, 20)),
    SlotRule("3:30", time(3, 30), time(5, 30)),
    SlotRule("5:40", time(5, 40), time(7, 40)),
    SlotRule("9:40", time(9, 40), time(11, 40)),
    SlotRule("11:50", time(11, 50), time(13, 50)),
    SlotRule("14:00", time(14), time(16)),
    SlotRule("16:10", time(16, 10), time(18, 10)),
    SlotRule("18:20", time(18, 20), time(20, 20)),
    SlotRule("20:30", time(20, 30), time(22, 30)),
    SlotRule("23:10", time(23, 10), time(1, 10)),
)

EXTERNAL_DRIVE_MWF_DAY_SLOTS = (
    SlotRule("11:40~13:00", time(11, 40), time(13)),
    SlotRule("13:00~14:00", time(13), time(14)),
    SlotRule("14:00~16:00", time(14), time(16)),
)

TOLERANCE_MINUTES = 8

