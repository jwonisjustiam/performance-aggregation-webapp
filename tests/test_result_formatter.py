from pathlib import Path

import pandas as pd

from processors.samsung_processor import process_samsung
from processors.weekly_processor import process_weekly
from services.excel_writer import create_result_workbook
from services.result_formatter import shorten_model
from services.validator import validate_saved_workbook


def test_model_shortening() -> None:
    assert shorten_model("SM-R390NZSAKOO") == "SM-R390"
    assert shorten_model("SM-L705NAW1KOO") == "SM-L705"


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

