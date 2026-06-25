from datetime import date

from services.time_slotter import assign_slot, slots_for_date


def test_next_day_0030_belongs_to_previous_last_slot() -> None:
    assert assign_slot("2026-06-23 00:30", "wearable") == (date(2026, 6, 22), "23:00")


def test_external_mwf_has_11_slots() -> None:
    assert len(slots_for_date("external", date(2026, 6, 22))) == 11


def test_external_other_day_has_10_slots() -> None:
    assert len(slots_for_date("external", date(2026, 6, 23))) == 10


def test_mwf_boundaries_choose_later_slot() -> None:
    assert assign_slot("2026-06-22 13:00", "external") == (date(2026, 6, 22), "13:00~14:00")
    assert assign_slot("2026-06-22 14:00", "external") == (date(2026, 6, 22), "14:00~16:00")


def test_wearable_has_10_slots() -> None:
    assert len(slots_for_date("wearable", date(2026, 6, 22))) == 10

