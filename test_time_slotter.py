from datetime import date

from services.time_slotter import assign_slot, slots_for_date


def test_next_day_0030_belongs_to_previous_last_slot() -> None:
    assert assign_slot("2026-06-23 00:30", "wearable") == (date(2026, 6, 22), "23:00")


def test_external_mwf_uses_default_10_slots() -> None:
    labels = [slot.label for slot in slots_for_date("external", date(2026, 6, 22))]
    assert len(labels) == 10
    assert "13:00~14:00" not in labels


def test_external_other_day_has_10_slots() -> None:
    assert len(slots_for_date("external", date(2026, 6, 23))) == 10


def test_external_default_boundaries_choose_nearest_slot() -> None:
    assert assign_slot("2026-06-22 13:55", "external") == (date(2026, 6, 22), "14:00")
    assert assign_slot("2026-06-22 16:05", "external") == (date(2026, 6, 22), "16:10")


def test_wearable_has_10_slots() -> None:
    assert len(slots_for_date("wearable", date(2026, 6, 22))) == 10


def test_wearable_20260703_override_has_split_11am_slots() -> None:
    labels = [slot.label for slot in slots_for_date("wearable", date(2026, 7, 3))]
    assert "11:00" in labels
    assert "11:40" in labels
    assert assign_slot("2026-07-03 11:10", "wearable") == (date(2026, 7, 3), "11:00")


def test_wearable_20260705_override_removes_1140_and_adds_custom_slots() -> None:
    labels = [slot.label for slot in slots_for_date("wearable", date(2026, 7, 5))]
    assert "11:40" not in labels
    assert {"13:00", "20:00", "20:20"}.issubset(labels)


def test_external_20260706_keeps_only_valid_sessions() -> None:
    labels = [slot.label for slot in slots_for_date("external", date(2026, 7, 6))]
    assert labels == ["1:20", "3:30", "5:40", "9:40", "11:50", "14:00"]
