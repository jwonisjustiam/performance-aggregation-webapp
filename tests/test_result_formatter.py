from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook

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
    workbook = load_workbook(path, data_only=False)
    try:
        sheet = workbook["회차별 합계"]
        assert sheet["B4"].value == "방송 정보"
        assert sheet["AA4"].value == "목표"
        assert sheet["AD4"].value == "실적"
        assert sheet["AJ4"].value == "AI라이브 대응"
        assert [sheet.cell(5, column).value for column in range(27, 34)] == [
            "View(만)", "수량", "금액(백만)", "View(만)", "수량", "전환율", "금액(백만)",
        ]
        assert sheet["AA8"].value == pytest.approx(0.1)
        assert sheet["AB8"].value == pytest.approx(50)
        assert sheet["AC8"].value == pytest.approx(10)
        assert sheet["AI8"].value == "=AG8/AC8"
        assert sheet["AJ8"].value == "쇼마젠시"
        for row in range(8, sheet.max_row + 1):
            assert sheet.cell(row, 32).value == f"=AE{row}/(AD{row}*10000)"
            assert sheet.cell(row, 32).number_format == "0.00%"
            assert sheet.cell(row, 35).value == f"=AG{row}/AC{row}"
            assert sheet.cell(row, 35).number_format == "0.00%"
        assert sheet.freeze_panes == "C8"
        assert workbook.calculation.calcMode in (None, "auto")
        assert workbook.calculation.fullCalcOnLoad is True
    finally:
        workbook.close()


def test_weekly_conversion_excel_format(weekly_frame: pd.DataFrame) -> None:
    stats = pd.DataFrame(
        [
            {
                "계정": "삼성공식파트너 쇼마젠시",
                "방송 ID": "100",
                "방송 제목": "외장하드 라이브",
                "방송일시": pd.Timestamp("2026-06-22 11:48"),
                "라이브중 시청수": 200,
                "유니크 결제자수": 5,
                "결제 상품수": 7,
                "데이터 업데이트 시각": pd.Timestamp("2026-06-23 10:00"),
            }
        ]
    )
    content, _ = create_result_workbook(
        "weekly", process_weekly(weekly_frame, "외장하드.xlsx", live_stats=stats)
    )
    workbook = load_workbook(BytesIO(content), data_only=False)
    try:
        sheet = workbook["회차별 합계"]
        headers = {cell.value: cell.column for cell in sheet[5]}
        row = next(
            row_number
            for row_number in range(8, sheet.max_row + 1)
            if sheet.cell(row_number, headers["시작 시간"]).value == "11:50"
        )
        cell = sheet.cell(row, headers["전환율"])
        assert cell.value == f"=AE{row}/(AD{row}*10000)"
        assert cell.number_format == "0.00%"
    finally:
        workbook.close()


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


@pytest.mark.parametrize("kind,target", [("external", 10), ("wearable", 24)])
def test_weekly_template_formula_cache_and_copy(kind, target):
    from datetime import date, time
    from openpyxl.formula.translate import Translator
    from rules.weekly_rules import SlotRule

    raw = pd.DataFrame([{
        "주문번호": "A", "결제일시": "2026-09-07 11:05", "상품명": "상품",
        "상품가격": 1_000_000, "옵션가격": 0, "주문 유입경로": "쇼핑라이브",
    }])
    stats = pd.DataFrame([{"방송일시": pd.Timestamp("2026-09-07 11:00"), "라이브중 시청수": 200, "데이터 업데이트 시각": pd.Timestamp("2026-09-08")}])
    result = process_weekly(raw, "주문.xlsx", kind, custom_slots={
        date(2026, 9, 7): (SlotRule("11:00", time(11), time(12)),),
    }, live_stats=stats)
    content, _ = create_result_workbook("weekly", result)
    formulas = load_workbook(BytesIO(content), data_only=False)
    cached = load_workbook(BytesIO(content), data_only=True)
    try:
        sheet = formulas.active
        assert sheet["C8"].value == 9
        assert sheet["J8"].value == "네이버"
        assert sheet["L8"].value == ("PP1" if kind == "external" else "PP2")
        assert sheet["T8"].value == ("Y3" if kind == "external" else "갤럭시워치9")
        assert sheet["U8"].value == (None if kind == "external" else "갤럭시링")
        assert sheet["AD8"].value == pytest.approx(0.02)
        assert sheet["AE8"].value == 1
        assert sheet["AG8"].value == 1
        assert cached.active["AF8"].value == pytest.approx(0.005)
        assert cached.active["AI8"].value == pytest.approx(1 / target)
        assert sheet["AF8"].number_format == sheet["AI8"].number_format == "0.00%"
        assert Translator(sheet["AF8"].value, origin="AF8").translate_formula("AF20") == "=AE20/(AD20*10000)"
        assert Translator(sheet["AI8"].value, origin="AI8").translate_formula("AI20") == "=AG20/AC20"
    finally:
        formulas.close()
        cached.close()
