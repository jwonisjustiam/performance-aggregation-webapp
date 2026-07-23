from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from processors.weekly_processor import process_weekly
from services.excel_writer import create_result_workbook


ROOT = Path(__file__).parents[1]


def test_streamlit_entrypoint_and_docs() -> None:
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "import streamlit as st" in app_source
    assert "streamlit==" in requirements
    assert "fastapi" not in requirements.lower()
    assert "Streamlit Cloud" in readme


def test_weekly_sample_can_create_downloadable_workbook() -> None:
    raw = pd.DataFrame(
        [["A", "2026-07-07 14:00", "외장하드", "옵션", 1_000_000, 0, "쇼핑라이브"]],
        columns=["주문번호", "결제일시", "상품명", "옵션 정보", "상품가격", "옵션가격", "주문 유입경로"],
    )
    result = process_weekly(raw, "외장하드.xlsx", "external")
    content, validation = create_result_workbook("weekly", result)

    assert validation["valid"] is True

    path = ROOT / "outputs" / "_test_streamlit_weekly.xlsx"
    path.write_bytes(content)
    workbook = load_workbook(path, read_only=True)
    try:
        assert workbook.sheetnames == ["회차별 합계"]
    finally:
        workbook.close()
        path.unlink(missing_ok=True)
