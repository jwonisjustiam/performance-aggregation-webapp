"""Amount parsing and source-specific amount resolution."""

from __future__ import annotations

import pandas as pd


def to_number(value: object) -> float | None:
    """Parse a spreadsheet number without inventing invalid values."""
    if value is None or pd.isna(value) or str(value).strip() == "":
        return 0.0
    cleaned = str(value).replace(",", "").replace("원", "").strip()
    try:
        return float(cleaned)
    except (TypeError, ValueError):
        return None


def resolve_amount(row: pd.Series) -> tuple[float | None, str]:
    """Resolve a row amount using the documented priority."""
    final = to_number(row.get("최종 상품별 총 주문금액"))
    if "최종 상품별 총 주문금액" in row.index and final is not None:
        return final, "최종 상품별 총 주문금액"
    product = to_number(row.get("상품가격"))
    option = to_number(row.get("옵션가격"))
    if product is None or option is None:
        return None, "상품가격 + 옵션가격"
    return product + option, "상품가격 + 옵션가격"


def to_millions(won: float) -> float:
    return round(float(won) / 1_000_000, 3)

