"""Business processors."""

from .samsung_processor import process_samsung
from .weekly_processor import process_weekly

__all__ = ["process_weekly", "process_samsung"]

