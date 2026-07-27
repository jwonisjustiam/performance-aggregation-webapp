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


def safe_datetime_series(value: object) -> pd.Series:
    if value is None:
        return pd.Series(dtype="datetime64[ns]")
    converted = pd.to_datetime(value, errors="coerce")
    if isinstance(converted, pd.Series):
        return converted
    if isinstance(converted, pd.DatetimeIndex):
        return pd.Series(converted)
    if pd.isna(converted):
        return pd.Series(dtype="datetime64[ns]")
    return pd.Series([converted])


def build_download_filename(
    job_type: str,
    result: dict[str, pd.DataFrame],
    payment_dates: pd.Series,
    weekly_kind: str | None = None,
) -> str:
    """Build a readable result filename from the actual type and result dates."""
    if job_type == "weekly":
        label = {"external": "외장하드", "wearable": "웨어러블"}.get(weekly_kind, "위클리")
        dates = safe_datetime_series(result["final"].get("날짜")).dropna()
    elif job_type == "detail":
        label = "워치9 사전판매"
        dates = safe_datetime_series(result["final"].get("결제일시")).dropna()
    else:
        label = "삼성"
        dates = safe_datetime_series(payment_dates).dropna()

    if dates.empty:
        date_text = "날짜미확인"
    else:
        first = dates.min().strftime("%Y%m%d")
        last = dates.max().strftime("%Y%m%d")
        date_text = first if first == last else f"{first}-{last}"
    return f"{label} {date_text} 정리본.xlsx"
