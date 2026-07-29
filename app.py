"""Streamlit entry point for the performance aggregation app."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
import tempfile
from inspect import signature
import hashlib
import json

import pandas as pd
import streamlit as st

from processors import process_detail, process_samsung, process_weekly
from processors.weekly_processor import MOBILE_ACC_SKUS, WEARABLE_SKUS, infer_target_dates, infer_weekly_kind
from services.excel_reader import XLS_ERROR, read_xlsx
from services.excel_writer import create_result_workbook
from services.time_slotter import slots_for_date
from services.validator import input_diagnostics
from rules.weekly_rules import SlotRule

MAX_UPLOAD_BYTES = 100 * 1024 * 1024
DEFAULT_SAMSUNG_MODEL_PREFIXES = ("SM-",)
CustomSlots = dict[date, tuple[SlotRule, ...]]

JOB_TYPE_OPTIONS = {
    "삼성 취합": {
        "code": "samsung",
        "title": "삼성 취합",
        "caption": "삼성 쇼핑라이브 Raw Data를 업로드해 통합 실적표, 회차별 합계, 중복 주문 검증 파일을 생성합니다.",
        "upload_label": "삼성 주문 Raw Data .xlsx 파일",
    },
    "위클리 취합": {
        "code": "weekly",
        "title": "위클리 취합",
        "caption": "외장하드 또는 웨어러블 Raw Data를 업로드해 회차별 수량과 금액을 집계합니다.",
        "upload_label": "위클리 주문 Raw Data .xlsx 파일",
    },
    "워치9 사전판매 판매 실적 취합": {
        "code": "detail",
        "title": "워치9 사전판매 판매 실적 취합",
        "caption": "Raw Data 전체에서 옵션 관리 코드 또는 판매자 상품 코드 기준으로 웨어러블/모바일 ACC 판매 실적 상세 목록을 생성합니다.",
        "upload_label": "워치9 사전판매 Raw Data .xlsx 파일",
    },
}


def format_rule_values(values: set[str]) -> str:
    return "\n".join(sorted(values))


def parse_rule_values(text: str) -> set[str]:
    values = []
    for chunk in str(text or "").replace(",", "\n").splitlines():
        cleaned = chunk.strip().upper()
        if cleaned:
            values.append(cleaned)
    return set(values)


def parse_prefix_values(text: str) -> tuple[str, ...]:
    return tuple(sorted(parse_rule_values(text)))


def safe_datetime_series(value: object) -> pd.Series:
    """Convert optional date-like input to a Series that always supports dropna()."""
    if value is None:
        return pd.Series(dtype="datetime64[ns]")
    converted = pd.to_datetime(value, errors="coerce")
    if isinstance(converted, pd.Series):
        return converted
    if isinstance(converted, pd.DatetimeIndex):
        return pd.Series(converted)
    if pd.isna(converted):
        return pd.Series(dtype="datetime64[ns]")
    return pd.Series([converted])


def parse_time_text(value: object) -> time:
    text = str(value or "").strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"시간 형식이 올바르지 않습니다: {text}. 예: 23:00")


def slot_duration_minutes(slot: SlotRule) -> int:
    base = date(2026, 1, 1)
    start = datetime.combine(base, slot.start)
    end = datetime.combine(base, slot.end)
    if end <= start:
        end += timedelta(days=1)
    return max(1, int((end - start).total_seconds() // 60))


def infer_uploaded_dates(uploaded_files: list[object]) -> list[date]:
    combined_names = " | ".join(Path(getattr(item, "name", "") or "").name for item in uploaded_files)
    return infer_target_dates(combined_names) or []


def uploaded_files_key(uploaded_files: list[object]) -> str:
    names = "|".join(Path(getattr(item, "name", "") or "").name for item in uploaded_files)
    return hashlib.sha1(names.encode("utf-8")).hexdigest()[:12]


def default_slot_rows(job_type: str, weekly_type: str | None, uploaded_files: list[object]) -> list[dict[str, object]]:
    target_dates = infer_uploaded_dates(uploaded_files)
    if not target_dates:
        return []
    combined_names = " | ".join(Path(getattr(item, "name", "") or "").name for item in uploaded_files)
    if job_type == "samsung":
        kind = "wearable"
    else:
        selected = None if weekly_type in {None, "", "auto"} else weekly_type
        kind = infer_weekly_kind(combined_names, selected)
    rows: list[dict[str, object]] = []
    for target in target_dates:
        for slot in slots_for_date(kind, target):
            rows.append(
                {
                    "사용": True,
                    "날짜": target.isoformat(),
                    "시작 시간": slot.start.strftime("%H:%M"),
                    "소요 시간(분)": slot_duration_minutes(slot),
                }
            )
    return rows


def normalize_template_sessions(rows: pd.DataFrame | list[dict[str, object]]) -> list[dict[str, object]]:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return []
    sessions: list[dict[str, object]] = []
    seen: set[tuple[str, int]] = set()
    for _, row in frame.iterrows():
        core_values = [row.get("시작 시간"), row.get("소요 시간(분)")]
        if all(pd.isna(value) or str(value).strip() == "" for value in core_values):
            continue
        use_value = row.get("사용", True)
        if pd.isna(use_value):
            use_value = True
        if not bool(use_value):
            continue
        start = parse_time_text(row.get("시작 시간")).strftime("%H:%M")
        duration = int(pd.to_numeric(row.get("소요 시간(분)"), errors="raise"))
        if duration <= 0:
            raise ValueError("소요 시간은 1분 이상이어야 합니다.")
        key = (start, duration)
        if key in seen:
            continue
        seen.add(key)
        sessions.append({"사용": True, "시작 시간": start, "소요 시간(분)": duration})
    return sessions


def template_sessions_to_slot_rows(sessions: list[dict[str, object]], uploaded_files: list[object]) -> list[dict[str, object]]:
    target_dates = infer_uploaded_dates(uploaded_files)
    rows: list[dict[str, object]] = []
    for target in target_dates:
        for session in sessions:
            rows.append(
                {
                    "사용": bool(session.get("사용", True)),
                    "날짜": target.isoformat(),
                    "시작 시간": parse_time_text(session.get("시작 시간")).strftime("%H:%M"),
                    "소요 시간(분)": int(pd.to_numeric(session.get("소요 시간(분)"), errors="raise")),
                }
            )
    return rows


def template_json_bytes(name: str, rows: pd.DataFrame) -> bytes:
    payload = {
        "name": name.strip() or "시간 템플릿",
        "sessions": normalize_template_sessions(rows),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def load_template_sessions(uploaded_template: object) -> list[dict[str, object]]:
    payload = json.loads(uploaded_template.getvalue().decode("utf-8-sig"))
    if isinstance(payload, list):
        sessions = payload
    elif isinstance(payload, dict):
        sessions = payload.get("sessions", [])
    else:
        raise ValueError("템플릿 JSON 형식이 올바르지 않습니다.")
    return normalize_template_sessions(sessions)


def slot_frame_key(frame: pd.DataFrame) -> str:
    text = frame.to_json(force_ascii=False, orient="records")
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def rows_to_custom_slots(rows: pd.DataFrame) -> CustomSlots:
    custom_slots: CustomSlots = {}
    if rows.empty:
        return custom_slots
    for _, row in rows.iterrows():
        core_values = [row.get("날짜"), row.get("시작 시간"), row.get("소요 시간(분)")]
        if all(pd.isna(value) or str(value).strip() == "" for value in core_values):
            continue
        use_value = row.get("사용", True)
        if pd.isna(use_value):
            use_value = True
        if not bool(use_value):
            continue
        target = pd.to_datetime(row.get("날짜"), errors="coerce")
        if pd.isna(target):
            raise ValueError(f"회차표 날짜가 올바르지 않습니다: {row.get('날짜')}")
        start = parse_time_text(row.get("시작 시간"))
        label = start.strftime("%H:%M")
        duration = int(pd.to_numeric(row.get("소요 시간(분)"), errors="raise"))
        if duration <= 0:
            raise ValueError("소요 시간은 1분 이상이어야 합니다.")
        end_dt = datetime.combine(target.date(), start) + timedelta(minutes=duration)
        slot = SlotRule(label, start, end_dt.time())
        custom_slots.setdefault(target.date(), tuple())
        custom_slots[target.date()] = (*custom_slots[target.date()], slot)
    return custom_slots


def slot_editor_height(row_count: int) -> int:
    """Return a tall-enough editor height so the schedule table does not feel cramped."""
    visible_rows = max(int(row_count) + 3, 8)
    return 80 + visible_rows * 35


def build_download_filename(
    job_type: str,
    result: dict[str, pd.DataFrame],
    payment_dates: pd.Series,
    weekly_kind: str | None = None,
) -> str:
    if job_type == "weekly":
        label = {"external": "외장하드", "wearable": "웨어러블"}.get(weekly_kind, "위클리")
        dates = safe_datetime_series(result["final"].get("날짜")).dropna()
    elif job_type == "detail":
        label = "워치9 사전판매"
        dates = safe_datetime_series(result["final"].get("결제일시")).dropna()
    else:
        label = "삼성"
        dates = safe_datetime_series(payment_dates).dropna()

    if dates.empty:
        date_text = "날짜미확인"
    else:
        first = dates.min().strftime("%Y%m%d")
        last = dates.max().strftime("%Y%m%d")
        date_text = first if first == last else f"{first}-{last}"
    return f"{label} {date_text} 정리본.xlsx"


def build_category_download_filename(category_label: str, frame: pd.DataFrame) -> str:
    dates = safe_datetime_series(frame.get("결제일시") if "결제일시" in frame else None).dropna()
    if dates.empty:
        date_text = "날짜미확인"
    else:
        first = dates.min().strftime("%Y%m%d")
        last = dates.max().strftime("%Y%m%d")
        date_text = first if first == last else f"{first}-{last}"
    return f"워치9 사전판매 {category_label} {date_text} 정리본.xlsx"


def create_single_sheet_workbook(sheet_name: str, frame: pd.DataFrame) -> tuple[bytes, dict[str, object]]:
    """Create one category workbook inside app.py to avoid partial-upload import failures."""
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "result.xlsx"
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            frame.to_excel(writer, sheet_name=sheet_name, index=False)
        return path.read_bytes(), {
            "valid": True,
            "missing_sheets": [],
            "formula_errors": [],
            "empty_sheets": [sheet_name] if frame.empty else [],
        }


def frame_summary(frame: pd.DataFrame, source_mode: str) -> dict[str, object]:
    payment = pd.to_datetime(frame.get("결제일시"), errors="coerce") if "결제일시" in frame else pd.Series(dtype="datetime64[ns]")
    live = frame.get("주문 유입경로", pd.Series(index=frame.index, dtype=object)).astype(str).str.strip().eq("쇼핑라이브")
    return {
        "입력 방식": source_mode,
        "통합 원본 행 수": len(frame),
        "통합 열 수": len(frame.columns),
        "최소 결제일": payment.min() if len(payment.dropna()) else None,
        "최대 결제일": payment.max() if len(payment.dropna()) else None,
        "쇼핑라이브 행 수": int(live.sum()),
        "쇼핑라이브 고유 주문번호 수": int(frame.loc[live, "주문번호"].nunique()) if "주문번호" in frame else 0,
    }


def uploaded_file_to_path(uploaded_file: object, target: Path) -> int:
    size = int(getattr(uploaded_file, "size", 0) or 0)
    if size > MAX_UPLOAD_BYTES:
        raise ValueError(f"{uploaded_file.name}: 파일 크기는 100MB 이하여야 합니다.")
    target.write_bytes(uploaded_file.getbuffer())
    return target.stat().st_size


def read_uploaded_workbooks(uploaded_files: list[object], temp_dir: Path) -> tuple[pd.DataFrame, str, list[dict[str, object]]]:
    if not uploaded_files:
        raise ValueError("주문 Raw Data .xlsx 파일을 한 개 이상 업로드해주세요.")

    workbooks = []
    file_info: list[dict[str, object]] = []
    for index, uploaded_file in enumerate(uploaded_files):
        name = Path(uploaded_file.name or f"upload_{index}").name
        suffix = Path(name).suffix.lower()
        if suffix == ".xls":
            raise ValueError(f"{name}: {XLS_ERROR}")
        if suffix != ".xlsx":
            raise ValueError(f"{name}: .xlsx 파일만 지원합니다.")

        path = temp_dir / f"{index:03d}_{name}"
        size = uploaded_file_to_path(uploaded_file, path)
        workbook = read_xlsx(path)
        workbooks.append(workbook)

        payment = pd.to_datetime(workbook.data.get("결제일시"), errors="coerce") if "결제일시" in workbook.data else pd.Series(dtype="datetime64[ns]")
        file_info.append(
            {
                "파일명": name,
                "파일 크기(KB)": round(size / 1024, 1),
                "시트 목록": ", ".join(workbook.sheet_names),
                "선택 시트": workbook.selected_sheet,
                "행 수": len(workbook.data),
                "열 수": len(workbook.data.columns),
                "암호화": "예" if workbook.encrypted else "아니오",
                "헤더 행": workbook.header_row,
                "최소 결제일": payment.min() if len(payment.dropna()) else None,
                "최대 결제일": payment.max() if len(payment.dropna()) else None,
            }
        )

    frame = pd.concat([item.data for item in workbooks], ignore_index=True, sort=False)
    combined_names = " | ".join(Path(item.name or "").name for item in uploaded_files)
    return frame, combined_names, file_info


def render_summary_cards(summary: dict[str, object], result: dict[str, pd.DataFrame]) -> None:
    columns = st.columns(4)
    columns[0].metric("원본 행 수", f"{int(summary['통합 원본 행 수']):,}")
    columns[1].metric("원본 열 수", f"{int(summary['통합 열 수']):,}")
    columns[2].metric("쇼핑라이브 행", f"{int(summary['쇼핑라이브 행 수']):,}")
    columns[3].metric("결과 행 수", f"{len(result['final']):,}")


def analyze_uploaded_files(
    job_type: str,
    weekly_type: str | None,
    uploaded_files: list[object],
    rule_settings: dict[str, object] | None = None,
) -> tuple[dict[str, pd.DataFrame], bytes, str, dict[str, object], list[dict[str, object]], dict[str, object], dict[str, object], int | None]:
    with tempfile.TemporaryDirectory() as temporary:
        temp_dir = Path(temporary)
        frame, combined_names, file_info = read_uploaded_workbooks(uploaded_files, temp_dir)
        return analyze_frame(job_type, weekly_type, frame, combined_names, file_info, rule_settings)


def analyze_frame(
    job_type: str,
    weekly_type: str | None,
    frame: pd.DataFrame,
    combined_names: str,
    file_info: list[dict[str, object]],
    rule_settings: dict[str, object] | None = None,
) -> tuple[dict[str, pd.DataFrame], bytes, str, dict[str, object], list[dict[str, object]], dict[str, object], dict[str, object], int | None]:
    payment_dates = pd.to_datetime(frame.get("결제일시"), errors="coerce") if "결제일시" in frame else pd.Series(dtype="datetime64[ns]")
    diagnostics = input_diagnostics(frame, ["주문번호", "결제일시", "상품명", "주문 유입경로"])
    common_orders = None

    if job_type == "weekly":
        selected = None if weekly_type in {None, "", "auto"} else weekly_type
        weekly_kind = infer_weekly_kind(combined_names, selected)
        weekly_kwargs = {}
        if "allowed_skus" in signature(process_weekly).parameters:
            weekly_kwargs["allowed_skus"] = None if rule_settings is None else rule_settings.get("weekly_skus")
        if "custom_slots" in signature(process_weekly).parameters:
            weekly_kwargs["custom_slots"] = None if rule_settings is None else rule_settings.get("custom_slots")
        result = process_weekly(frame, combined_names, selected, **weekly_kwargs)
    elif job_type == "detail":
        weekly_kind = None
        detail_kwargs = {}
        detail_parameters = signature(process_detail).parameters
        if "wearable_skus" in detail_parameters:
            detail_kwargs["wearable_skus"] = None if rule_settings is None else rule_settings.get("wearable_skus")
        if "mobile_acc_skus" in detail_parameters:
            detail_kwargs["mobile_acc_skus"] = None if rule_settings is None else rule_settings.get("mobile_acc_skus")
        result = process_detail(frame, combined_names, None, **detail_kwargs)
    else:
        weekly_kind = None
        samsung_kwargs = {}
        if "model_prefixes" in signature(process_samsung).parameters:
            samsung_kwargs["model_prefixes"] = None if rule_settings is None else rule_settings.get("samsung_model_prefixes")
        if "custom_slots" in signature(process_samsung).parameters:
            samsung_kwargs["custom_slots"] = None if rule_settings is None else rule_settings.get("custom_slots")
        result = process_samsung(frame, combined_names, **samsung_kwargs)

    filename = build_download_filename(job_type, result, payment_dates, weekly_kind)
    if job_type == "detail":
        content = b""
        validation = {
            "valid": True,
            "missing_sheets": [],
            "formula_errors": [],
            "empty_sheets": [],
            "note": "워치9 사전판매 결과는 웨어러블/모바일 ACC 별도 다운로드에서 생성합니다.",
        }
    else:
        content, validation = create_result_workbook(job_type, result)
    summary = frame_summary(frame, "엑셀 직접 업로드")
    return result, content, filename, summary, file_info, diagnostics, validation, common_orders


def render_usage_guide() -> None:
    with st.expander("사용 안내", expanded=False):
        st.markdown(
            """
            1. 왼쪽에서 `업무 유형`을 먼저 선택하세요.
            2. 업무 유형은 `삼성 취합`, `위클리 취합`, `워치9 사전판매 판매 실적 취합` 3가지입니다.
            3. 삼성 취합은 `삼성 모델/SKU 시작값`을 화면에서 수정할 수 있습니다. 기본값은 `SM-`입니다.
            4. 위클리 취합은 `외장하드` 또는 `웨어러블` 유형을 선택한 뒤 주문 Raw Data 엑셀을 업로드하세요.
            5. 위클리 취합은 `위클리 포함 SKU 목록`을 비워두면 기존처럼 전체 쇼핑라이브 주문을 취합하고, 값을 입력하면 해당 SKU만 취합합니다.
            6. 워치9 사전판매 판매 실적 취합은 라이브 시간/회차 규칙 없이 옵션 관리 코드 또는 판매자 상품 코드의 SKU 목록으로 `웨어러블`, `모바일 ACC` 두 결과를 만듭니다.
            7. 워치9 사전판매 판매 실적 취합에서는 화면의 SKU 목록을 직접 수정한 뒤 분석할 수 있습니다.
            8. 업로드 파일은 `.xlsx`만 지원합니다. `.xls` 파일은 엑셀에서 `.xlsx`로 저장한 뒤 올려주세요.
            """
        )


def main() -> None:
    st.set_page_config(page_title="실적 취합 도구", page_icon="📊", layout="wide")

    with st.sidebar:
        st.header("작업 설정")
        job_type_label = st.selectbox("업무 유형", list(JOB_TYPE_OPTIONS))
        selected_job = JOB_TYPE_OPTIONS[job_type_label]
        job_type = selected_job["code"]
        weekly_type = None
        rule_settings: dict[str, object] = {}
        if job_type == "weekly":
            weekly_label = st.selectbox("위클리 유형", ["자동 판정", "외장하드", "웨어러블"])
            weekly_type = {"자동 판정": "auto", "외장하드": "external", "웨어러블": "wearable"}[weekly_label]
            st.subheader("위클리 분류 규칙")
            st.caption("비워두면 기존처럼 모든 쇼핑라이브 주문을 취합합니다. 특정 SKU만 취합하려면 옵션 관리 코드 또는 판매자 상품 코드를 입력하세요.")
            weekly_rule_text = st.text_area(
                "위클리 포함 SKU 목록",
                value="",
                height=120,
                placeholder="예: SM-R390NZSAKOO, ET-SNL34SBEGKR",
            )
            rule_settings["weekly_skus"] = parse_rule_values(weekly_rule_text)
        elif job_type == "samsung":
            st.subheader("삼성 분류 규칙")
            st.caption("기본값은 SM- 전체입니다. 쉼표 또는 줄바꿈으로 시작값을 수정할 수 있습니다.")
            samsung_prefix_text = st.text_area(
                "삼성 모델/SKU 시작값",
                value=format_rule_values(set(DEFAULT_SAMSUNG_MODEL_PREFIXES)),
                height=90,
            )
            rule_settings["samsung_model_prefixes"] = parse_prefix_values(samsung_prefix_text)
        elif job_type == "detail":
            st.subheader("워치9 분류 규칙")
            st.caption("쉼표 또는 줄바꿈으로 구분해서 수정할 수 있습니다. 비워두면 해당 버전 결과가 0건으로 나옵니다.")
            wearable_rule_text = st.text_area(
                "웨어러블 SKU 목록",
                value=format_rule_values(WEARABLE_SKUS),
                height=160,
            )
            mobile_acc_rule_text = st.text_area(
                "모바일 ACC SKU 목록",
                value=format_rule_values(MOBILE_ACC_SKUS),
                height=220,
            )
            rule_settings.update({
                "wearable_skus": parse_rule_values(wearable_rule_text),
                "mobile_acc_skus": parse_rule_values(mobile_acc_rule_text),
            })

    st.title(selected_job["title"])
    st.caption(selected_job["caption"])
    st.caption("배포 버전: 2026-07-29 시간표 저장·불러오기")
    render_usage_guide()

    st.subheader(f"{selected_job['title']} Raw Data 업로드")
    uploaded_files = st.file_uploader(
        selected_job["upload_label"],
        type=["xlsx"],
        accept_multiple_files=True,
        key=f"raw_files_{job_type}",
    )

    if job_type in {"samsung", "weekly"} and uploaded_files:
        with st.expander("회차 시간 설정", expanded=True):
            st.caption(
                "파일명에서 작업 대상 날짜를 읽어 날짜별 회차표를 자동 생성합니다. "
                "필요하면 날짜/시작 시간/소요 시간을 직접 수정하거나 행을 추가·삭제할 수 있습니다."
            )
            try:
                if "slot_templates" not in st.session_state:
                    st.session_state["slot_templates"] = {}

                slot_rows = default_slot_rows(job_type, weekly_type, uploaded_files)
                if slot_rows:
                    template_key_parts = ["default"]
                    saved_templates: dict[str, list[dict[str, object]]] = st.session_state["slot_templates"]
                    if saved_templates:
                        selected_template = st.selectbox(
                            "저장된 시간 템플릿 불러오기",
                            ["자동 생성값 사용"] + sorted(saved_templates),
                            key=f"template_select_{job_type}_{weekly_type}_{uploaded_files_key(uploaded_files)}",
                        )
                        if selected_template != "자동 생성값 사용":
                            slot_rows = template_sessions_to_slot_rows(saved_templates[selected_template], uploaded_files)
                            template_key_parts.append(selected_template)

                    uploaded_template = st.file_uploader(
                        "시간 템플릿 JSON 파일 불러오기",
                        type=["json"],
                        key=f"slot_template_upload_{job_type}_{weekly_type}_{uploaded_files_key(uploaded_files)}",
                    )
                    if uploaded_template is not None:
                        imported_sessions = load_template_sessions(uploaded_template)
                        slot_rows = template_sessions_to_slot_rows(imported_sessions, uploaded_files)
                        template_key_parts.append(uploaded_template.name)

                    slot_frame = pd.DataFrame(slot_rows)
                    st.caption(
                        "행 추가: 표 맨 아래 빈 행에 입력합니다. "
                        "행 제외: `사용` 체크를 끄거나 행을 삭제합니다. "
                        "`날짜`는 YYYY-MM-DD, `시작 시간`은 HH:MM 형식으로 입력합니다."
                    )
                    edited_slots = st.data_editor(
                        slot_frame,
                        use_container_width=True,
                        hide_index=True,
                        num_rows="dynamic",
                        height=slot_editor_height(len(slot_frame)),
                        column_config={
                            "사용": st.column_config.CheckboxColumn("사용"),
                            "날짜": st.column_config.TextColumn("날짜", help="YYYY-MM-DD 형식으로 입력"),
                            "시작 시간": st.column_config.TextColumn("시작 시간", help="HH:MM 형식으로 입력"),
                            "소요 시간(분)": st.column_config.NumberColumn("소요 시간(분)", min_value=1, step=1),
                        },
                        key=f"slot_editor_{job_type}_{weekly_type}_{uploaded_files_key(uploaded_files)}_{slot_frame_key(slot_frame)}_{hashlib.sha1('|'.join(template_key_parts).encode('utf-8')).hexdigest()[:8]}",
                    )
                    rule_settings["custom_slots"] = rows_to_custom_slots(edited_slots)
                    st.divider()
                    template_name = st.text_input(
                        "현재 시간표 템플릿 이름",
                        value=f"{selected_job['title']} 시간 템플릿",
                        key=f"slot_template_name_{job_type}_{weekly_type}_{uploaded_files_key(uploaded_files)}",
                    )
                    save_col, download_col = st.columns(2)
                    with save_col:
                        if st.button(
                            "현재 시간표 임시 저장",
                            key=f"slot_template_save_{job_type}_{weekly_type}_{uploaded_files_key(uploaded_files)}",
                        ):
                            st.session_state["slot_templates"][template_name.strip() or "시간 템플릿"] = normalize_template_sessions(edited_slots)
                            st.success("현재 접속 중 사용할 수 있는 시간 템플릿으로 저장했습니다.")
                    with download_col:
                        st.download_button(
                            "현재 시간표 JSON 다운로드",
                            data=template_json_bytes(template_name, edited_slots),
                            file_name=f"{template_name.strip() or '시간_템플릿'}.json",
                            mime="application/json",
                            key=f"slot_template_download_{job_type}_{weekly_type}_{uploaded_files_key(uploaded_files)}",
                        )
                else:
                    st.info("파일명에서 작업 대상 날짜를 찾지 못했습니다. 예: `20260724~20260726` 형식이 있으면 회차표를 자동 생성합니다.")
            except Exception as exc:
                st.warning(f"회차표를 만들 수 없습니다: {exc}")

    if st.button("분석 시작", type="primary"):
        try:
            with st.spinner("엑셀을 읽고 실적을 취합 중입니다."):
                result, content, filename, summary, file_info, diagnostics, validation, common_orders = analyze_uploaded_files(
                    job_type,
                    weekly_type,
                    uploaded_files,
                    rule_settings,
                )
            show_result(job_type, result, content, filename, summary, file_info, diagnostics, validation, common_orders)
        except Exception as exc:
            st.error(f"처리할 수 없습니다: {exc}")


def show_result(
    job_type: str,
    result: dict[str, pd.DataFrame],
    content: bytes,
    filename: str,
    summary: dict[str, object],
    file_info: list[dict[str, object]],
    diagnostics: dict[str, object],
    validation: dict[str, object],
    common_orders: int | None,
) -> None:
    st.success("분석과 저장 후 재검증을 완료했습니다.")
    render_summary_cards(summary, result)
    if job_type == "detail":
        download_columns = st.columns(2)
        wearable_content, wearable_validation = create_single_sheet_workbook("웨어러블", result.get("wearable", pd.DataFrame()))
        mobile_acc_content, mobile_acc_validation = create_single_sheet_workbook("모바일 ACC", result.get("mobile_acc", pd.DataFrame()))
        download_columns[0].download_button(
            "웨어러블 결과 엑셀 다운로드",
            data=wearable_content,
            file_name=build_category_download_filename("웨어러블", result.get("wearable", pd.DataFrame())),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
        download_columns[1].download_button(
            "모바일 ACC 결과 엑셀 다운로드",
            data=mobile_acc_content,
            file_name=build_category_download_filename("모바일 ACC", result.get("mobile_acc", pd.DataFrame())),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        validation = {
            **validation,
            "분리파일검증": {
                "웨어러블": wearable_validation,
                "모바일_ACC": mobile_acc_validation,
            },
        }
    else:
        st.download_button(
            "결과 엑셀 다운로드",
            data=content,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
    st.subheader("최종 결과 미리보기")
    if result["final"].empty:
        st.warning("분류 조건에 맞는 결과 행이 없습니다. 입력 파일의 옵션 관리 코드 또는 판매자 상품 코드를 확인해주세요.")
    st.dataframe(result["final"], use_container_width=True)
    if file_info:
        with st.expander("입력 파일 정보", expanded=False):
            st.dataframe(pd.DataFrame(file_info), use_container_width=True)
    with st.expander("검사 및 저장 검증", expanded=False):
        st.json(
            {
                "입력검사": diagnostics,
                "저장후검증": validation,
                "방송실적표_공통주문번호": common_orders,
            }
        )


if __name__ == "__main__":
    main()
