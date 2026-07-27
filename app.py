"""Streamlit entry point for the performance aggregation app."""

from __future__ import annotations

from pathlib import Path
import tempfile

import pandas as pd
import streamlit as st

from processors import process_detail, process_samsung, process_weekly
from processors.weekly_processor import infer_weekly_kind
from services.excel_reader import XLS_ERROR, read_xlsx
from services.excel_writer import create_result_workbook
from services.validator import input_diagnostics

MAX_UPLOAD_BYTES = 100 * 1024 * 1024

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
) -> tuple[dict[str, pd.DataFrame], bytes, str, dict[str, object], list[dict[str, object]], dict[str, object], dict[str, object], int | None]:
    with tempfile.TemporaryDirectory() as temporary:
        temp_dir = Path(temporary)
        frame, combined_names, file_info = read_uploaded_workbooks(uploaded_files, temp_dir)
        return analyze_frame(job_type, weekly_type, frame, combined_names, file_info)


def analyze_frame(
    job_type: str,
    weekly_type: str | None,
    frame: pd.DataFrame,
    combined_names: str,
    file_info: list[dict[str, object]],
) -> tuple[dict[str, pd.DataFrame], bytes, str, dict[str, object], list[dict[str, object]], dict[str, object], dict[str, object], int | None]:
    payment_dates = pd.to_datetime(frame.get("결제일시"), errors="coerce") if "결제일시" in frame else pd.Series(dtype="datetime64[ns]")
    diagnostics = input_diagnostics(frame, ["주문번호", "결제일시", "상품명", "주문 유입경로"])
    common_orders = None

    if job_type == "weekly":
        selected = None if weekly_type in {None, "", "auto"} else weekly_type
        weekly_kind = infer_weekly_kind(combined_names, selected)
        result = process_weekly(frame, combined_names, selected)
    elif job_type == "detail":
        weekly_kind = None
        result = process_detail(frame, combined_names, None)
    else:
        weekly_kind = None
        result = process_samsung(frame, combined_names)

    filename = build_download_filename(job_type, result, payment_dates, weekly_kind)
    content, validation = create_result_workbook(job_type, result)
    summary = frame_summary(frame, "엑셀 직접 업로드")
    return result, content, filename, summary, file_info, diagnostics, validation, common_orders


def render_usage_guide() -> None:
    st.info(
        """
        **사용 안내**

        1. 왼쪽에서 `업무 유형`을 먼저 선택하세요.
        2. 업무 유형은 `삼성 취합`, `위클리 취합`, `워치9 사전판매 판매 실적 취합` 3가지입니다.
        3. 위클리 취합은 `외장하드` 또는 `웨어러블` 유형을 선택한 뒤 주문 Raw Data 엑셀을 업로드하세요.
        4. 워치9 사전판매 판매 실적 취합은 라이브 시간/회차 규칙 없이 옵션 관리 코드 또는 판매자 상품 코드의 지정 SKU 목록으로 `웨어러블`, `모바일 ACC` 두 결과를 만듭니다.
        5. 삼성 취합은 주문 Raw Data 엑셀만 업로드하면 됩니다.
        6. 업로드 파일은 `.xlsx`만 지원합니다. `.xls` 파일은 엑셀에서 `.xlsx`로 저장한 뒤 올려주세요.
        7. `분석 시작`을 누르면 결과 미리보기와 `결과 엑셀 다운로드` 버튼이 표시됩니다.
        """,
        icon="ℹ️",
    )


def main() -> None:
    st.set_page_config(page_title="실적 취합 도구", page_icon="📊", layout="wide")

    with st.sidebar:
        st.header("작업 설정")
        job_type_label = st.selectbox("업무 유형", list(JOB_TYPE_OPTIONS))
        selected_job = JOB_TYPE_OPTIONS[job_type_label]
        job_type = selected_job["code"]
        weekly_type = None
        if job_type == "weekly":
            weekly_label = st.selectbox("위클리 유형", ["자동 판정", "외장하드", "웨어러블"])
            weekly_type = {"자동 판정": "auto", "외장하드": "external", "웨어러블": "wearable"}[weekly_label]

    st.title(selected_job["title"])
    st.caption(selected_job["caption"])
    render_usage_guide()

    st.subheader(f"{selected_job['title']} Raw Data 업로드")
    uploaded_files = st.file_uploader(
        selected_job["upload_label"],
        type=["xlsx"],
        accept_multiple_files=True,
        key=f"raw_files_{job_type}",
    )

    if st.button("분석 시작", type="primary"):
        try:
            with st.spinner("엑셀을 읽고 실적을 취합 중입니다."):
                result, content, filename, summary, file_info, diagnostics, validation, common_orders = analyze_uploaded_files(
                    job_type,
                    weekly_type,
                    uploaded_files,
                )
            show_result(result, content, filename, summary, file_info, diagnostics, validation, common_orders)
        except Exception as exc:
            st.error(f"처리할 수 없습니다: {exc}")


def show_result(
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
