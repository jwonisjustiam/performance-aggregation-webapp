"""Flexible, cross-platform Excel input reader."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

import pandas as pd
from openpyxl import load_workbook

from services.file_security import readable_workbook

XLS_ERROR = "현재 버전에서는 .xlsx 파일만 지원합니다. .xls 파일은 xlsx로 변환 후 다시 업로드해주세요."

ALIASES = {
    "주문번호": ("주문번호", "order id"),
    "상품주문번호": ("상품주문번호", "상품 주문번호"),
    "결제일시": ("결제일시", "결제일", "결제 일시"),
    "상품명": ("상품명", "상품 이름"),
    "수량": ("수량", "상품수량"),
    "옵션관리코드": ("옵션관리코드", "옵션 관리 코드"),
    "판매자 상품코드": ("판매자 상품코드", "판매자상품코드"),
    "상품가격": ("상품가격", "상품 가격"),
    "옵션가격": ("옵션가격", "옵션 가격"),
    "최종 상품별 총 주문금액": ("최종 상품별 총 주문금액", "최종상품별총주문금액"),
    "주문 유입경로": ("주문 유입경로", "주문유입경로", "쇼핑라이브 여부"),
}


@dataclass
class WorkbookData:
    data: pd.DataFrame
    sheet_names: list[str]
    selected_sheet: str
    header_row: int | str
    encrypted: bool


def normalize_label(value: object) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def canonicalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename recognized source columns to canonical business names."""
    normalized = {normalize_label(column): column for column in df.columns}
    rename: dict[object, str] = {}
    for canonical, aliases in ALIASES.items():
        for alias in aliases:
            found = normalized.get(normalize_label(alias))
            if found is not None:
                rename[found] = canonical
                break
    result = df.rename(columns=rename)
    if "주문번호" not in result and "상품주문번호" in result:
        result["주문번호"] = result["상품주문번호"]
    return result


def _detect_header_row_with_score(path: Path, sheet_name: str, scan_rows: int = 30) -> tuple[int, int]:
    """Find the most likely header row and its recognized-column score."""
    preview = pd.read_excel(path, sheet_name=sheet_name, header=None, nrows=scan_rows, engine="openpyxl")
    known = {normalize_label(alias) for aliases in ALIASES.values() for alias in aliases}
    scores = []
    for index, row in preview.iterrows():
        score = sum(normalize_label(value) in known for value in row if pd.notna(value))
        scores.append((score, int(index)))
    best_score, best_index = max(scores, default=(0, 0))
    if best_score < 2:
        return 0, best_score
    return best_index, best_score


def detect_header_row(path: Path, sheet_name: str, scan_rows: int = 30) -> int:
    """Find the most likely header row using recognized column aliases."""
    header_row, _ = _detect_header_row_with_score(path, sheet_name, scan_rows)
    return header_row


def _looks_like_order_sheet(frame: pd.DataFrame) -> bool:
    """Return True for sheets that look like raw order data."""
    recognized = {
        "주문번호",
        "상품주문번호",
        "결제일시",
        "상품명",
        "수량",
        "주문 유입경로",
        "옵션관리코드",
        "판매자 상품코드",
    }
    present = recognized.intersection(set(map(str, frame.columns)))
    return len(present) >= 3 and not frame.dropna(how="all").empty


def read_xlsx(path: Path, sheet_name: str | None = None) -> WorkbookData:
    """Read an xlsx workbook, including supported encrypted files."""
    if path.suffix.lower() != ".xlsx":
        raise ValueError(XLS_ERROR)
    with readable_workbook(path) as (readable, encrypted):
        workbook = load_workbook(readable, read_only=True, data_only=False)
        try:
            sheets = list(workbook.sheetnames)
        finally:
            workbook.close()
        target_sheets = [sheet_name] if sheet_name in sheets else sheets
        frames: list[pd.DataFrame] = []
        selected_sheets: list[str] = []
        header_rows: list[str] = []
        for current_sheet in target_sheets:
            header_row, header_score = _detect_header_row_with_score(readable, current_sheet)
            frame = pd.read_excel(readable, sheet_name=current_sheet, header=header_row, engine="openpyxl")
            frame = canonicalize_columns(frame.dropna(how="all").reset_index(drop=True))
            if sheet_name in sheets or header_score >= 2 and _looks_like_order_sheet(frame):
                frame["원본시트"] = current_sheet
                frames.append(frame)
                selected_sheets.append(current_sheet)
                header_rows.append(f"{current_sheet}:{header_row + 1}")

        if frames:
            combined = pd.concat(frames, ignore_index=True, sort=False)
            selected = ", ".join(selected_sheets)
            header_row_text: int | str = ", ".join(header_rows)
        else:
            selected = sheets[0]
            header_row = detect_header_row(readable, selected)
            combined = pd.read_excel(readable, sheet_name=selected, header=header_row, engine="openpyxl")
            combined = canonicalize_columns(combined.dropna(how="all").reset_index(drop=True))
            header_row_text = header_row + 1
    return WorkbookData(combined, sheets, selected, header_row_text, encrypted)


def first_present(columns: Iterable[object], candidates: Iterable[str]) -> str | None:
    lookup = {normalize_label(column): str(column) for column in columns}
    for candidate in candidates:
        if normalize_label(candidate) in lookup:
            return lookup[normalize_label(candidate)]
    return None
