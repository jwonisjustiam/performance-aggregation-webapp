from __future__ import annotations

import pandas as pd
import pytest

from services.excel_reader import canonicalize_columns


def test_kakao_columns_are_canonicalized() -> None:
    raw = pd.DataFrame(
        [
            {
                "결제번호": "PAY-1",
                "주문번호": "ORDER-1",
                "주문일": "2026-07-29 14:00",
                "상품명": "갤럭시 워치9 SM-L340N",
                "수량": 1,
                "상품금액": 300_000,
                "옵션금액": 0,
                "옵션코드": "SM-L340NZEAKOO",
                "톡딜여부": "-",
            }
        ]
    )
    result = canonicalize_columns(raw, "카카오 raw.xlsx")
    assert result.loc[0, "원본몰"] == "카카오"
    assert result.loc[0, "결제일시"] == "2026-07-29 14:00"
    assert result.loc[0, "상품가격"] == 300_000
    assert result.loc[0, "옵션관리코드"] == "SM-L340NZEAKOO"


def test_gmarket_and_auction_are_detected_per_row_and_sku_is_derived() -> None:
    raw = pd.DataFrame(
        [
            {
                "판매아이디": "지마켓(shop)",
                "주문번호": "G-1",
                "결제일": "2026-07-29 14:00",
                "상품명": "갤럭시 워치9 SM-L340N",
                "옵션": "색상:크림{ZEAKOO}/1개",
                "수량": 1,
                "판매금액": 300_000,
            },
            {
                "판매아이디": "옥션(shop)",
                "주문번호": "A-1",
                "결제일": "2026-07-29 14:00",
                "상품명": "갤럭시 워치9 SM-L350N",
                "옵션": "색상:실버{ZSAKOO}/1개",
                "수량": 1,
                "판매금액": 350_000,
            },
        ]
    )
    result = canonicalize_columns(raw, "지마켓, 옥션 raw.xlsx")
    assert list(result["원본몰"]) == ["지마켓", "옥션"]
    assert list(result["옵션관리코드"]) == ["SM-L340NZEAKOO", "SM-L350NZSAKOO"]
    assert list(result["최종 상품별 총 주문금액"]) == [300_000, 350_000]


def test_11st_modified_columns_are_canonicalized() -> None:
    raw = pd.DataFrame(
        [
            {
                "예약결제완료일시": "2026/07/29",
                "주문번호": "11-1",
                "주문상세번호": "11-1-1",
                "상품명": "갤럭시 워치9 SM-L340N",
                "옵션": "색상:크림[ZEAKOO]-1개",
                "수량": 1,
                "주문금액": 300_000,
                "서비스이용료정책": "동의",
            }
        ]
    )
    result = canonicalize_columns(raw, "11번가 raw.xls")
    assert result.loc[0, "원본몰"] == "11번가"
    assert result.loc[0, "상품주문번호"] == "11-1-1"
    assert result.loc[0, "옵션관리코드"] == "SM-L340NZEAKOO"
    assert "원본 구분 열 없음" in result.loc[0, "쇼핑라이브 판정근거"]


@pytest.mark.parametrize(
    "date_header",
    ["결제일시", "예약결제완료일시", "주문일시", "결제일"],
)
def test_payment_date_aliases_and_product_name_sku_are_recognized(date_header: str) -> None:
    raw = pd.DataFrame(
        [
            {
                "주문번호": "ORDER-1",
                date_header: "2026.07.30",
                "상품명": "삼성전자 갤럭시 워치9 블루투스 44mm SM-L350N 리뷰신세계2만+강화유리2매",
                "수량": 1,
                "판매금액": 350_000,
            }
        ]
    )
    result = canonicalize_columns(raw, "주문 raw.xlsx")
    assert "결제일시" in result
    assert pd.to_datetime(result.loc[0, "결제일시"], errors="coerce") == pd.Timestamp("2026-07-30")
    assert result.loc[0, "옵션관리코드"] == "SM-L350N"
