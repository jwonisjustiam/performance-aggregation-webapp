"""Result table formatting helpers."""

from __future__ import annotations

import re

import pandas as pd


def shorten_model(value: object) -> str:
    """Reduce a Samsung SKU to its SM-prefix and numeric model."""
    match = re.search(r"\b(SM-[A-Z]*\d+)", str(value or "").upper())
    return match.group(1) if match else ""


def sort_models(df: pd.DataFrame, model_column: str = "모델") -> pd.DataFrame:
    if df.empty:
        return df
    result = df.copy()
    result["_priority"] = result[model_column].map(lambda value: (0, value) if value == "SM-R390" else (1, value))
    return result.sort_values("_priority", kind="stable").drop(columns="_priority").reset_index(drop=True)


def build_download_filename(
    job_type: str,
    result: dict[str, pd.DataFrame],
    payment_dates: pd.Series,
    weekly_kind: str | None = None,
) -> str:
    """Build a readable result filename from the actual type and result dates."""
    if job_type == "weekly":
        label = {"external": "외장하드", "wearable": "웨어러블"}.get(weekly_kind, "위클리")
        dates = pd.to_datetime(result["final"].get("날짜"), errors="coerce").dropna()
    else:
        label = "삼성"
        dates = pd.to_datetime(payment_dates, errors="coerce").dropna()

    if dates.empty:
        date_text = "날짜미확인"
    else:
        first = dates.min().strftime("%Y%m%d")
        last = dates.max().strftime("%Y%m%d")
        date_text = first if first == last else f"{first}-{last}"
    return f"{label} {date_text} 정리본.xlsx"
