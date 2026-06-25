"""Samsung aggregation configuration."""

from rules.weekly_rules import WEARABLE_SLOTS

SAMSUNG_SLOTS = WEARABLE_SLOTS
DEFAULT_BROADCAST_VALUES = {
    "플랫폼": "네이버",
    "제작 주체": "AI",
    "Duration (분)": 120,
    "담당/SOP": "쇼마젠시",
    "View(만)": 0,
}
MODEL_PRIORITY = ("SM-R390",)

