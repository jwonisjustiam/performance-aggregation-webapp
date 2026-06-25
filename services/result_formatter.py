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

