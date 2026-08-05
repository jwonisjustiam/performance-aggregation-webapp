from pathlib import Path

import pandas as pd

from processors.samsung_processor import process_samsung
from processors.weekly_processor import process_detail, process_weekly
from services.excel_writer import create_result_workbook
from services.result_formatter import build_download_filename, shorten_model
from services.validator import validate_saved_workbook


def test_model_shortening() -> None:
    assert shorten_model("SM-R390NZSAKOO") == "SM-R390"
    assert shorten_model("SM-L705NAW1KOO") == "SM-L705"


def test_weekly_download_filename_includes_type_and_date() -> None:
    result = {"final": pd.DataFrame({"날짜": ["2026-06-24"]})}
    name = build_download_filename("weekly", result, pd.Series(dtype=object), "external")
    assert name == "외장하드 20260624 정리본.xlsx"


def test_weekly_download_filename_uses_date_range() -> None:
    result = {"final": pd.DataFrame({"날짜": ["2026-06-24", "2026-06-25"]})}
    name = build_download_filename("weekly", result, pd.Series(dtype=object), "wearable")
    assert name == "웨어러블 20260624-20260625 정리본.xlsx"


def test_weekly_workbook_reopens(tmp_path: Path, weekly_frame: pd.DataFrame) -> None:
    content, validation = create_result_workbook("weekly", process_weekly(weekly_frame, "외장하드.xlsx"))
    path = tmp_path / "weekly result.xlsx"
    path.write_bytes(content)
    assert validation["valid"]
    assert validate_saved_workbook(path, ["회차별 합계"])["valid"]


def test_samsung_workbook_reopens(tmp_path: Path, samsung_frame: pd.DataFrame) -> None:
    content, validation = create_result_workbook("samsung", process_samsung(samsung_frame))
    path = tmp_path / "samsung result.xlsx"
    path.write_bytes(content)
    assert validation["valid"]
    assert validate_saved_workbook(path, ["통합 실적표", "회차별 합계", "중복 주문 검증"])["valid"]


def test_detail_workbook_reopens(tmp_path: Path) -> None:
    raw = pd.DataFrame(
        [
            ["A", "2026-07-07 14:00", "갤럭시 워치9", "", "SM-L340NZEAKOO", 1_000_000, 0],
            ["B", "2026-07-07 15:00", "충전 어댑터", "EF-QF976CTEGKR", "SELLER-B", 500_000, 0],
        ],
        columns=["주문번호", "결제일시", "상품명", "옵션관리코드", "판매자 상품코드", "상품가격", "옵션가격"],
    )
    content, validation = create_result_workbook("detail", process_detail(raw, "주문.xlsx"))
    path = tmp_path / "detail result.xlsx"
    path.write_bytes(content)
    assert validation["valid"]
    assert validate_saved_workbook(path, ["Basic", "웨어러블", "모바일 ACC"])["valid"]
