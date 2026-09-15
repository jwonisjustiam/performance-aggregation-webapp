"""Generate styled, validated result workbooks."""

from __future__ import annotations

from pathlib import Path
import tempfile

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from services.validator import validate_saved_workbook


def _style(path: Path, sheet_formats: dict[str, dict[str, str]]) -> None:
    workbook = load_workbook(path)
    try:
        for sheet in workbook.worksheets:
            sheet.freeze_panes = "A2"
            sheet.sheet_view.showGridLines = False
            for cell in sheet[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="1F4E78")
            for column_cells in sheet.columns:
                width = min(max(len(str(cell.value or "")) for cell in column_cells) + 2, 45)
                sheet.column_dimensions[column_cells[0].column_letter].width = max(width, 10)
            formats = sheet_formats.get(sheet.title, {})
            header_map = {cell.value: cell.column for cell in sheet[1]}
            for header, number_format in formats.items():
                if header in header_map:
                    for row in range(2, sheet.max_row + 1):
                        sheet.cell(row, header_map[header]).number_format = number_format
        workbook.save(path)
    finally:
        workbook.close()


def _style_weekly_report(path: Path) -> None:
    """Apply grouped target/actual headers to the weekly output."""
    workbook = load_workbook(path)
    try:
        sheet = workbook["회차별 합계"]
        sheet.freeze_panes = "J8"
        sheet.sheet_view.showGridLines = False
        group_fill = PatternFill("solid", fgColor="FFF200")
        info_fill = PatternFill("solid", fgColor="D9EAF7")
        column_fill = PatternFill("solid", fgColor="E7E6E6")
        input_fill = PatternFill("solid", fgColor="FFF2CC")
        thin = Side(style="thin", color="7F7F7F")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        groups = [
            ("J6:Z6", "방송 정보", info_fill),
            ("AA6:AC6", "목표", group_fill),
            ("AD6:AG6", "실적", group_fill),
            ("AH6:AI6", "성과", group_fill),
            ("AJ6:AK6", "AI라이브 대응", group_fill),
        ]
        for cell_range, label, fill in groups:
            sheet.merge_cells(cell_range)
            cell = sheet[cell_range.split(":")[0]]
            cell.value = label
            cell.fill = fill
            cell.font = Font(bold=True, color="C00000" if fill == group_fill else "1F1F1F")
            cell.alignment = Alignment(horizontal="center", vertical="center")
            for row in sheet[cell_range]:
                for item in row:
                    item.border = border
                    item.fill = fill

        display_headers = [
            "월", "일", "요일", "시작 시간", "duration", "ai 여부", "재방송여부", "채널", "방송주체",
            "운영그룹", "운영파트", "삼성 담당자", "거래선1", "거래선2", "품목1", "품목2", "비고",
            "View(만)", "수량", "금액(백만)", "View(만)", "수량", "전환율", "금액(백만)",
            "비용률", "달성률", "제작(대행사)", "출연자1",
        ]
        for column, header in enumerate(display_headers, start=10):
            cell = sheet.cell(7, column)
            cell.value = header
            cell.fill = column_fill
            cell.font = Font(bold=True, color="1F1F1F")
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = border

        for row in range(8, sheet.max_row + 1):
            for column in range(10, 38):
                cell = sheet.cell(row, column)
                cell.border = border
                cell.alignment = Alignment(horizontal="center", vertical="center")
                if 16 <= column <= 26:
                    cell.fill = input_fill
            sheet.cell(row, 27).number_format = "0.0"
            sheet.cell(row, 28).number_format = "0.0"
            sheet.cell(row, 29).number_format = "0.0"
            sheet.cell(row, 30).number_format = "0.###"
            sheet.cell(row, 31).number_format = "0"
            sheet.cell(row, 32).value = f"=AE{row}/(AD{row}*10000)"
            sheet.cell(row, 32).number_format = "0.00%"
            sheet.cell(row, 33).number_format = "0.###"
            sheet.cell(row, 34).number_format = '0.00"%"'
            sheet.cell(row, 35).value = f"=AG{row}/AC{row}"
            sheet.cell(row, 35).number_format = "0.00%"

        widths = [5, 5, 6, 11, 10, 9, 12, 10, 11, 11, 11, 13, 10, 10, 15, 15, 12, 10, 9, 12, 10, 9, 10, 12, 9, 9, 13, 10]
        for column, width in enumerate(widths, start=10):
            sheet.column_dimensions[sheet.cell(7, column).column_letter].width = width
        sheet.row_dimensions[6].height = 24
        sheet.row_dimensions[7].height = 32
        workbook.calculation.calcMode = "auto"
        workbook.calculation.fullCalcOnLoad = True
        workbook.calculation.forceFullCalc = True
        workbook.save(path)
    finally:
        workbook.close()


def create_result_workbook(job_type: str, result: dict[str, pd.DataFrame]) -> tuple[bytes, dict[str, object]]:
    """Create the required workbook, reopen it, and return bytes plus validation."""
    if job_type == "weekly":
        required = ["회차별 합계"]
    elif job_type == "detail":
        required = ["Basic", "웨어러블", "모바일 ACC"]
    else:
        required = ["통합 실적표", "회차별 합계", "중복 주문 검증"]
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "result.xlsx"
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            if job_type == "weekly":
                result["final"].to_excel(writer, sheet_name="회차별 합계", index=False, startrow=6, startcol=9)
            elif job_type == "detail":
                result.get("basic", pd.DataFrame()).to_excel(writer, sheet_name="Basic", index=False)
                result.get("wearable", pd.DataFrame()).to_excel(writer, sheet_name="웨어러블", index=False)
                result.get("mobile_acc", pd.DataFrame()).to_excel(writer, sheet_name="모바일 ACC", index=False)
            else:
                result["final"].to_excel(writer, sheet_name="통합 실적표", index=False)
                result["summary"].to_excel(writer, sheet_name="회차별 합계", index=False)
                result["duplicates"].to_excel(writer, sheet_name="중복 주문 검증", index=False)
        if job_type == "weekly":
            _style_weekly_report(path)
        else:
            _style(
                path,
                {
                    "회차별 합계": {"금액(백만)": "0.###", "총 금액": "#,##0", "duration (분)": "0", "수량": "0", "전환율": '0.00"%"'},
                    "Basic": {"금액": "#,##0", "주문번호": "@"},
                    "웨어러블": {"금액": "#,##0", "주문번호": "@"},
                    "모바일 ACC": {"금액": "#,##0", "주문번호": "@"},
                    "통합 실적표": {"실적(대)": "0", "Duration (분)": "0", "DURATION (분)": "0", "View(만)": "0.###"},
                    "중복 주문 검증": {"주문 금액": "#,##0"},
                },
            )
        validation = validate_saved_workbook(path, required, allow_empty_sheets=job_type == "detail")
        if not validation["valid"]:
            raise ValueError(f"결과 파일 검증 실패: {validation}")
        return path.read_bytes(), validation


def create_single_sheet_workbook(sheet_name: str, frame: pd.DataFrame, allow_empty: bool = True) -> tuple[bytes, dict[str, object]]:
    """Create one downloadable workbook for one result category."""
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "result.xlsx"
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            frame.to_excel(writer, sheet_name=sheet_name, index=False)
        _style(path, {sheet_name: {"금액": "#,##0", "주문번호": "@"}})
        validation = validate_saved_workbook(path, [sheet_name], allow_empty_sheets=allow_empty)
        if not validation["valid"]:
            raise ValueError(f"결과 파일 검증 실패: {validation}")
        return path.read_bytes(), validation
