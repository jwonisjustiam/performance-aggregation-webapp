from datetime import date, time

import pandas as pd

from processors.samsung_processor import process_samsung
from rules.weekly_rules import SlotRule


def test_only_sm_and_model_shortening(samsung_frame: pd.DataFrame) -> None:
    result = process_samsung(samsung_frame)
    models = set(result["final"]["모델"]) - {""}
    assert models == {"SM-R390", "SM-L705"}
    assert not any(model.startswith(("EF-", "EP-", "GP-", "EB-", "EI-")) for model in models)


def test_r390_priority_and_multi_model_representative(samsung_frame: pd.DataFrame) -> None:
    result = process_samsung(samsung_frame)
    populated = result["final"][result["final"]["모델"] != ""]
    assert populated.iloc[0]["모델"] == "SM-R390"
    order = result["duplicates"].query("주문번호 == 'S3'").iloc[0]
    assert order["대표 모델"] == "SM-L705"
    assert "복수 SM" in order["처리 기준"]


def test_integrated_and_summary_counts_match(samsung_frame: pd.DataFrame) -> None:
    result = process_samsung(samsung_frame)
    assert result["final"]["실적(대)"].sum() == sum(value for value in result["summary"]["총 주문수"] if value != "")


def test_seller_code_sm_is_used_when_option_code_is_non_sm() -> None:
    frame = pd.DataFrame(
        [["S1", "2026-06-22 01:20", "워치", 1, "EF-CASE", "SM-L320NDAAKOO", 200_000, 0, "쇼핑라이브"]],
        columns=["주문번호", "결제일시", "상품명", "수량", "옵션관리코드", "판매자 상품코드", "상품가격", "옵션가격", "주문 유입경로"],
    )
    result = process_samsung(frame)
    models = set(result["final"]["모델"]) - {""}
    assert models == {"SM-L320"}


def test_samsung_uses_wearable_date_override_slots() -> None:
    frame = pd.DataFrame(
        [["S1", "2026-07-05 20:05", "워치", 1, "SM-R390NZSAKOO", "", 200_000, 0, "쇼핑라이브"]],
        columns=["주문번호", "결제일시", "상품명", "수량", "옵션관리코드", "판매자 상품코드", "상품가격", "옵션가격", "주문 유입경로"],
    )
    result = process_samsung(frame)
    assert "11:40" not in set(result["final"]["시간"])
    assert {"13:00", "20:00", "20:20"}.issubset(set(result["final"]["시간"]))


def test_samsung_manual_slots_override_naver_download_timestamp_in_file_name() -> None:
    frame = pd.DataFrame(
        [["S1", "2026-07-31 20:09", "워치", 1, "SM-R390NZSAKOO", "", 200_000, 0, "쇼핑라이브"]],
        columns=["주문번호", "결제일시", "상품명", "수량", "옵션관리코드", "판매자 상품코드", "상품가격", "옵션가격", "주문 유입경로"],
    )
    custom_slots = {
        date(2026, 7, 31): (SlotRule("20:00", time(20, 0), time(21, 0)),),
    }

    result = process_samsung(
        frame,
        "스마트스토어_전체주문발주발송관리_20260803_0921.xlsx",
        custom_slots=custom_slots,
    )

    assert set(zip(result["final"]["월"], result["final"]["일"])) == {(7, 31)}
    assert result["final"]["실적(대)"].sum() == 1


def test_samsung_period_file_outputs_all_target_dates_and_excludes_after_last_midnight_window() -> None:
    frame = pd.DataFrame(
        [
            ["S1", "2026-07-24 01:20", "워치", 1, "SM-R390NZSAKOO", "", 200_000, 0, "쇼핑라이브"],
            ["S2", "2026-07-25 01:20", "워치", 1, "SM-L320NDAAKOO", "", 200_000, 0, "쇼핑라이브"],
            ["S3", "2026-07-26 01:20", "워치", 1, "SM-L705NAW1KOO", "", 200_000, 0, "쇼핑라이브"],
            ["S4", "2026-07-27 00:30", "워치", 1, "SM-R390NZSAKOO", "", 200_000, 0, "쇼핑라이브"],
            ["S5", "2026-07-27 01:09", "워치", 1, "SM-R390NZSAKOO", "", 200_000, 0, "쇼핑라이브"],
        ],
        columns=["주문번호", "결제일시", "상품명", "수량", "옵션관리코드", "판매자 상품코드", "상품가격", "옵션가격", "주문 유입경로"],
    )
    result = process_samsung(frame, "웨어러블 20260724~20260726 금~일 데이터 1.xlsx")
    summary = result["summary"]
    assert set(zip(summary["월"], summary["일"])) == {(7, 24), (7, 25), (7, 26)}
    assert sum(value for value in summary["총 주문수"] if value != "") == 4
    excluded = result["duplicates"].query("주문번호 == 'S5'").iloc[0]
    assert "회차 범위 밖" in excluded["처리 기준"]


def test_samsung_uses_sm_code_from_product_name_without_code_columns() -> None:
    frame = pd.DataFrame(
        [
            {
                "주문번호": "S1",
                "결제일시": "2026-07-23 01:20",
                "상품명": "삼성전자 갤럭시 워치9 블루투스 44mm SM-L350N 리뷰신세계2만+강화유리2매",
                "수량": 1,
                "상품가격": 350_000,
                "옵션가격": 0,
                "주문 유입경로": "쇼핑라이브",
            }
        ]
    )
    result = process_samsung(frame, "웨어러블 20260723.xlsx")
    assert set(result["final"]["모델"]) - {""} == {"SM-L350"}
