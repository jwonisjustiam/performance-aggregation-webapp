"""Generate styled, validated result workbooks."""

from __future__ import annotations

from pathlib import Path
import tempfile

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill
import xlsxwriter

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


# Match the supplied report, including the gaps for hidden template columns.
WEEKLY_EXCEL_COLUMNS = {
    "월": "C", "일": "D", "요일": "E", "시작 시간": "F", "duration": "G",
    "ai 여부": "H", "재방송여부": "I", "채널": "J", "방송주체": "K",
    "운영그룹": "L", "운영파트": "M", "삼성 담당자": "N", "거래선1": "O",
    "품목1": "T", "품목2": "U", "비고": "V", "목표 View(만)": "AA",
    "목표 수량": "AB", "목표 금액(백만)": "AC", "실적 View(만)": "AD",
    "실적 수량": "AE", "실적 전환율": "AF", "실적 금액(백만)": "AG",
    "비용률": "AH", "달성률": "AI", "제작(대행사)": "AJ", "출연자1": "AK",
}


def _write_weekly_report(path: Path, frame: pd.DataFrame) -> None:
    """Write formulas and their cached results without an openpyxl resave."""
    with xlsxwriter.Workbook(path) as workbook:
        sheet = workbook.add_worksheet("회차별 합계")
        sheet.freeze_panes(7, 2)
        sheet.hide_gridlines(2)
        workbook.set_calc_mode("auto")
        base = {"border": 1, "align": "center", "valign": "vcenter"}
        text_format = workbook.add_format(base)
        number_format = workbook.add_format({**base, "num_format": "0.###"})
        percent_format = workbook.add_format({**base, "num_format": "0.00%"})
        header_format = workbook.add_format({**base, "bold": True, "bg_color": "#E7E6E6"})
        group_format = workbook.add_format({**base, "bold": True, "bg_color": "#FFF200"})
        sheet.merge_range("B4:V4", "방송 정보", group_format)
        sheet.merge_range("AA4:AC4", "목표", group_format)
        sheet.merge_range("AD4:AH4", "실적", group_format)
        sheet.merge_range("AJ4:AM4", "AI라이브 대응", group_format)
        sheet.write("B5", "번호", header_format)
        for name, column in WEEKLY_EXCEL_COLUMNS.items():
            header = name.removeprefix("목표 ").removeprefix("실적 ")
            sheet.write(f"{column}5", header, header_format)
            sheet.set_column(f"{column}:{column}", 13 if name != "삼성 담당자" else 18)
        sheet.write("AL5", "출연자2", header_format)
        sheet.write("AM5", "스튜디오", header_format)
        sheet.set_column("B:E", 5)
        sheet.set_column("T:U", 20)
        sheet.set_column("P:S", None, None, {"hidden": True})
        sheet.set_column("W:Z", None, None, {"hidden": True})
        for excel_row, (_, record) in enumerate(frame.iterrows(), start=8):
            sheet.write_number(f"B{excel_row}", excel_row - 7, text_format)
            for name, column in WEEKLY_EXCEL_COLUMNS.items():
                if name in {"실적 전환율", "달성률"}:
                    continue
                value = record[name]
                if pd.isna(value) or value == "":
                    sheet.write_blank(f"{column}{excel_row}", None, text_format)
                elif isinstance(value, (int, float)):
                    sheet.write_number(f"{column}{excel_row}", value, number_format)
                else:
                    sheet.write_string(f"{column}{excel_row}", str(value), text_format)
            views = record["실적 View(만)"]
            target = record["목표 금액(백만)"]
            conversion = "#DIV/0!" if pd.isna(views) or views == 0 else record["실적 수량"] / (views * 10000)
            achievement = "#DIV/0!" if pd.isna(target) or target == 0 else record["실적 금액(백만)"] / target
            sheet.write_formula(f"AF{excel_row}", f"=AE{excel_row}/(AD{excel_row}*10000)", percent_format, conversion)
            sheet.write_formula(f"AI{excel_row}", f"=AG{excel_row}/AC{excel_row}", percent_format, achievement)


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
        if job_type == "weekly":
            _write_weekly_report(path, result["final"])
        else:
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                if job_type == "detail":
                    result.get("basic", pd.DataFrame()).to_excel(writer, sheet_name="Basic", index=False)
                    result.get("wearable", pd.DataFrame()).to_excel(writer, sheet_name="웨어러블", index=False)
                    result.get("mobile_acc", pd.DataFrame()).to_excel(writer, sheet_name="모바일 ACC", index=False)
                else:
                    result["final"].to_excel(writer, sheet_name="통합 실적표", index=False)
                    result["summary"].to_excel(writer, sheet_name="회차별 합계", index=False)
                    result["duplicates"].to_excel(writer, sheet_name="중복 주문 검증", index=False)
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
