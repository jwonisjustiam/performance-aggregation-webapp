import pandas as pd
import pytest

from processors.weekly_processor import infer_weekly_kind, process_weekly


def test_unique_order_count_and_multiple_line_amount(weekly_frame: pd.DataFrame) -> None:
    result = process_weekly(weekly_frame, "외장하드 주문.xlsx")
    row = result["final"].query("시간 == '11:50'").iloc[0]
    assert row["수량"] == 2
    assert row["금액(백만)"] == 1.501
    assert result["extra_details"].empty


def test_midnight_and_empty_slots_are_kept(weekly_frame: pd.DataFrame) -> None:
    result = process_weekly(weekly_frame, "외장하드 주문.xlsx")["final"]
    assert result.query("시간 == '23:10'")["수량"].sum() == 1
    assert (result["수량"] == 0).any()


def test_exact_duplicate_removed(weekly_frame: pd.DataFrame) -> None:
    duplicated = pd.concat([weekly_frame, weekly_frame.iloc[[0]]], ignore_index=True)
    result = process_weekly(duplicated, "외장하드.xlsx")
    assert len(result["duplicates"]) == 1
    assert result["final"]["금액(백만)"].sum() == pytest.approx(1.502)


def test_shifted_live_detection(weekly_frame: pd.DataFrame) -> None:
    result = process_weekly(weekly_frame, "외장하드.xlsx")
    assert result["final"]["수량"].sum() == 4


def test_multiple_raw_files_are_combined_and_deduplicated(weekly_frame: pd.DataFrame) -> None:
    first = weekly_frame.iloc[:3]
    second = weekly_frame.iloc[[0, 3, 4]]
    combined = pd.concat([first, second], ignore_index=True)
    result = process_weekly(combined, "외장하드 1.xlsx | 외장하드 2.xlsx")
    assert len(result["duplicates"]) == 1
    assert result["final"]["수량"].sum() == 4


def test_mixed_weekly_file_types_are_rejected() -> None:
    with pytest.raises(ValueError, match="혼합"):
        infer_weekly_kind("외장하드.xlsx | 웨어러블.xlsx")


def test_product_order_number_duplicate_removed() -> None:
    frame = pd.DataFrame(
        [
            ["A", "P1", "2026-06-22 13:00", "상품1", "옵션", 1_000_000, 0, "쇼핑라이브"],
            ["A", "P1", "2026-06-22 13:00", "상품1", "옵션", 1_000_000, 0, "쇼핑라이브"],
        ],
        columns=["주문번호", "상품주문번호", "결제일시", "상품명", "옵션 정보", "상품가격", "옵션가격", "주문 유입경로"],
    )
    result = process_weekly(frame, "외장하드.xlsx")
    assert len(result["duplicates"]) == 1
    assert result["final"]["금액(백만)"].sum() == pytest.approx(1)


def test_disabled_wearable_session_orders_are_excluded() -> None:
    frame = pd.DataFrame(
        [["W1", "2026-07-18 13:55", "웨어러블", 1, 100_000, 0, "쇼핑라이브"]],
        columns=["주문번호", "결제일시", "상품명", "수량", "상품가격", "옵션가격", "주문 유입경로"],
    )
    result = process_weekly(frame, "웨어러블.xlsx")
    assert result["final"].query("시간 == '13:50'")["수량"].iloc[0] == 0
    assert len(result["excluded"]) == 1
