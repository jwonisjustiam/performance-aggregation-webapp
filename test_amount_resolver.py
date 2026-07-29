import pandas as pd

from services.amount_resolver import resolve_amount, to_millions


def test_amount_priority_and_fallback() -> None:
    assert resolve_amount(pd.Series({"최종 상품별 총 주문금액": 300, "상품가격": 100, "옵션가격": 20}))[0] == 300
    assert resolve_amount(pd.Series({"상품가격": 100, "옵션가격": 20}))[0] == 120


def test_million_conversion_and_zero() -> None:
    assert to_millions(1_234_567) == 1.235
    assert to_millions(0) == 0

