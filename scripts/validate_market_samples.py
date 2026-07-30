"""Print privacy-safe metadata for supported raw-order workbook samples."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.excel_reader import read_workbook
from processors.samsung_processor import process_samsung
from processors.weekly_processor import process_detail


CANONICAL_COLUMNS = (
    "주문번호",
    "상품주문번호",
    "결제일시",
    "상품명",
    "수량",
    "옵션관리코드",
    "판매자 상품코드",
    "상품가격",
    "옵션가격",
    "최종 상품별 총 주문금액",
    "주문 유입경로",
    "원본몰",
)


def validate(path: Path) -> dict[str, object]:
    workbook = read_workbook(path)
    samsung = process_samsung(workbook.data, path.name)
    detail = process_detail(workbook.data, path.name)
    markets = (
        sorted(set(workbook.data["원본몰"].dropna().astype(str)))
        if "원본몰" in workbook.data
        else []
    )
    return {
        "file": path.name,
        "encrypted": workbook.encrypted,
        "sheets": workbook.sheet_names,
        "selected_sheets": workbook.selected_sheet,
        "header_rows": workbook.header_row,
        "rows": len(workbook.data),
        "markets": markets,
        "canonical_columns": [column for column in CANONICAL_COLUMNS if column in workbook.data],
        "samsung_nonzero_units": int(samsung["final"]["실적(대)"].sum()),
        "detail_wearable_rows": len(detail["wearable"]),
        "detail_mobile_acc_rows": len(detail["mobile_acc"]),
    }


for value in sys.argv[1:]:
    path = Path(value)
    try:
        result = validate(path)
    except Exception as exc:
        result = {"file": path.name, "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, ensure_ascii=False, default=str))
