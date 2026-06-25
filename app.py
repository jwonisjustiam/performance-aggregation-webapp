"""Streamlit entry point for the performance aggregation web app."""

from __future__ import annotations

from pathlib import Path
import tempfile

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from processors import process_samsung, process_weekly
from processors.weekly_processor import infer_weekly_kind
from services.excel_reader import XLS_ERROR, read_xlsx
from services.excel_writer import create_result_workbook
from services.naver_commerce import fetch_raw_data
from services.validator import input_diagnostics

load_dotenv()


def build_download_filename(
    job_type: str,
    result: dict[str, pd.DataFrame],
    payment_dates: pd.Series,
    weekly_kind: str | None = None,
) -> str:
    """Build a readable result filename from the type and result dates."""
    if job_type == "weekly":
        label = {"external": "외장하드", "wearable": "웨어러블"}.get(weekly_kind, "위클리")
        dates = pd.to_datetime(result["final"].get("날짜"), errors="coerce").dropna()
    else:
        label = "삼성"
        dates = pd.to_datetime(payment_dates, errors="coerce").dropna()

    if dates.empty:
        date_text = "날짜미확인"
    else:
        first = dates.min().strftime("%Y%m%d")
        last = dates.max().strftime("%Y%m%d")
        date_text = first if first == last else f"{first}-{last}"
    return f"{label} {date_text} 정리본.xlsx"


st.set_page_config(page_title="삼성 라이브 실적 정리 도구", page_icon="📊", layout="wide")
st.title("삼성 라이브 실적 정리 도구")
st.write("Raw Data를 업로드하거나 네이버 커머스 API에서 가져와 실적을 정리합니다.")

with st.expander("사용 안내", expanded=True):
    st.markdown(
        """
        1. **업무 유형**을 선택합니다.
        2. 위클리 작업은 네이버 API 자동 수집 또는 엑셀 업로드를 선택할 수 있습니다.
        3. 원본 정보와 검사 결과를 확인한 뒤 **분석 시작**을 누릅니다.
        4. 처리 결과를 확인하고 **결과 엑셀 다운로드**를 누릅니다.

        - 외장하드와 웨어러블은 서로 다른 API 계정으로 독립 수집합니다.
        - API 수집 결과에 다른 계정 유형이 섞이면 분석을 중단합니다.
        - 엑셀 업로드에서도 외장하드와 웨어러블 파일을 한 번에 섞지 마세요.
        - 주문 Raw Data는 **결제일 기준 전일~당일** 범위를 권장합니다.
        """
    )

job_column, type_column = st.columns([2, 1])
with job_column:
    job_label = st.radio("업무 유형", ["위클리 실적 취합", "삼성 실적 취합"], horizontal=True)
job_type = "weekly" if job_label.startswith("위클리") else "samsung"

source_mode = "엑셀 직접 업로드"
weekly_type = None
api_kind = None
with type_column:
    if job_type == "weekly":
        source_mode = st.selectbox("Raw Data 방식", ["네이버 API 자동 수집", "엑셀 직접 업로드"])

uploaded_files = []
api_frame = None
if source_mode == "네이버 API 자동 수집":
    account_column, start_column, end_column = st.columns(3)
    with account_column:
        account_label = st.selectbox("수집 계정", ["웨어러블", "외장하드"])
    api_kind = {"웨어러블": "wearable", "외장하드": "external"}[account_label]
    with start_column:
        start_date = st.date_input("결제일 시작")
    with end_column:
        end_date = st.date_input("결제일 종료")
    weekly_type = account_label
    st.caption("선택한 계정 한 개만 호출하며 두 계정의 Raw Data를 자동으로 합치지 않습니다.")
    if st.button("네이버 Raw Data 가져오기", type="primary"):
        try:
            with st.spinner(f"{account_label} 주문 Raw Data를 가져오는 중입니다."):
                fetched = fetch_raw_data(api_kind, start_date, end_date)
            st.session_state["naver_api_frame"] = fetched
            st.session_state["naver_api_kind"] = api_kind
            st.session_state["naver_api_range"] = (start_date, end_date)
            st.success(f"{account_label} Raw Data {len(fetched):,}행을 가져왔습니다.")
        except Exception as exc:
            st.error(f"네이버 API 수집 실패: {exc}")
    if st.session_state.get("naver_api_kind") == api_kind:
        api_frame = st.session_state.get("naver_api_frame")
elif job_type == "weekly":
    with type_column:
        weekly_type = st.selectbox("위클리 유형", ["자동 판정", "외장하드", "웨어러블"])

if source_mode == "엑셀 직접 업로드":
    uploaded_files = st.file_uploader(
        "주문 Raw Data (.xlsx, 1개 이상)",
        type=None,
        accept_multiple_files=True,
    )

broadcast_uploaded = None
if job_type == "samsung":
    broadcast_uploaded = st.file_uploader("방송 실적표 (.xlsx, 선택)", type=None, key="broadcast")

if uploaded_files or api_frame is not None:
    with tempfile.TemporaryDirectory() as temporary:
        file_info_rows = []
        if api_frame is not None:
            frame = api_frame.copy()
            combined_names = f"{weekly_type}_네이버_API"
            observed_kinds = set(frame.get("API 계정 유형", pd.Series(dtype=object)).dropna())
            if not frame.empty and observed_kinds != {api_kind}:
                st.error("API Raw Data에 다른 계정 유형이 섞여 있어 처리를 중단했습니다.")
                st.stop()
        else:
            workbooks = []
            for index, uploaded in enumerate(uploaded_files):
                suffix = Path(uploaded.name).suffix.lower()
                if suffix == ".xls":
                    st.error(f"{uploaded.name}: {XLS_ERROR}")
                    st.stop()
                if suffix != ".xlsx":
                    st.error(f"{uploaded.name}: 지원하지 않는 파일입니다. .xlsx 파일을 업로드해주세요.")
                    st.stop()
                path = Path(temporary) / f"{index:03d}_{Path(uploaded.name).name}"
                path.write_bytes(uploaded.getvalue())
                try:
                    workbook = read_xlsx(path)
                except Exception as exc:
                    st.error(f"{uploaded.name}: {exc}")
                    st.stop()
                workbooks.append(workbook)
                file_payment = (
                    pd.to_datetime(workbook.data.get("결제일시"), errors="coerce")
                    if "결제일시" in workbook.data
                    else pd.Series(dtype="datetime64[ns]")
                )
                file_info_rows.append(
                    {
                        "파일명": uploaded.name,
                        "파일 크기(KB)": round(uploaded.size / 1024, 1),
                        "시트 목록": ", ".join(workbook.sheet_names),
                        "선택 시트": workbook.selected_sheet,
                        "행 수": len(workbook.data),
                        "열 수": len(workbook.data.columns),
                        "암호화": "예" if workbook.encrypted else "아니오",
                        "헤더 행": workbook.header_row,
                        "최소 결제일": file_payment.min(),
                        "최대 결제일": file_payment.max(),
                    }
                )
            frame = pd.concat([workbook.data for workbook in workbooks], ignore_index=True, sort=False)
            combined_names = " | ".join(uploaded.name for uploaded in uploaded_files)

        payment = (
            pd.to_datetime(frame.get("결제일시"), errors="coerce")
            if "결제일시" in frame
            else pd.Series(dtype="datetime64[ns]")
        )
        live = (
            frame.get("주문 유입경로", pd.Series(index=frame.index, dtype=object))
            .astype(str)
            .str.strip()
            .eq("쇼핑라이브")
        )
        info = {
            "입력 방식": source_mode,
            "통합 원본 행 수": len(frame),
            "통합 열 수": len(frame.columns),
            "최소 결제일": payment.min(),
            "최대 결제일": payment.max(),
            "쇼핑라이브 행 수": int(live.sum()),
            "쇼핑라이브 고유 주문번호 수": int(frame.loc[live, "주문번호"].nunique()) if "주문번호" in frame else 0,
        }
        if file_info_rows:
            st.subheader("파일 기본 정보")
            st.dataframe(pd.DataFrame(file_info_rows), use_container_width=True, hide_index=True)
        else:
            st.subheader("API Raw Data 미리보기")
            st.dataframe(frame.head(100), use_container_width=True, hide_index=True)

        with st.expander("통합 원본 정보", expanded=False):
            st.dataframe(pd.DataFrame(info.items(), columns=["항목", "값"]), use_container_width=True, hide_index=True)
            if len(payment.dropna()):
                daily = payment.dt.date.value_counts().sort_index().rename_axis("날짜").reset_index(name="원본 행 수")
                st.dataframe(daily, use_container_width=True, hide_index=True)

        required = ["주문번호", "결제일시", "상품명", "주문 유입경로"]
        diagnostics = input_diagnostics(frame, required)
        with st.expander("파일 검사 결과", expanded=False):
            st.json(diagnostics)

        if st.button("분석 시작", type="primary"):
            try:
                weekly_kind = None
                if job_type == "weekly":
                    selected = {"외장하드": "external", "웨어러블": "wearable"}.get(weekly_type)
                    weekly_kind = infer_weekly_kind(combined_names, selected)
                    result = process_weekly(frame, combined_names, selected)
                else:
                    broadcast_frame = None
                    if broadcast_uploaded is not None:
                        if Path(broadcast_uploaded.name).suffix.lower() != ".xlsx":
                            raise ValueError(XLS_ERROR)
                        broadcast_path = Path(temporary) / f"broadcast_{Path(broadcast_uploaded.name).name}"
                        broadcast_path.write_bytes(broadcast_uploaded.getvalue())
                        broadcast_frame = read_xlsx(broadcast_path).data
                        if "주문번호" in frame and "주문번호" in broadcast_frame:
                            common = len(set(frame["주문번호"].dropna()) & set(broadcast_frame["주문번호"].dropna()))
                            st.info(f"주문 원본과 방송 실적표의 공통 주문번호: {common}건")
                    result = process_samsung(frame, optional_broadcast_df=broadcast_frame)
                download_name = build_download_filename(job_type, result, payment, weekly_kind)
                content, validation = create_result_workbook(job_type, result)
                st.success("분석과 저장 후 재검증을 완료했습니다.")
                st.dataframe(result["final"], use_container_width=True, hide_index=True)
                if not result["extra_details"].empty:
                    st.subheader("외장하드 13:00~14:00 상세")
                    st.dataframe(result["extra_details"], use_container_width=True, hide_index=True)
                st.download_button(
                    "결과 엑셀 다운로드",
                    data=content,
                    file_name=download_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                st.caption(f"저장 후 검증: {validation}")
            except Exception as exc:
                st.error(f"처리할 수 없습니다: {exc}")
import requests

if st.button("서버 IP 확인"):
    server_ip = requests.get(
        "https://api.ipify.org",
        timeout=10,
    ).text.strip()

    st.info(f"Streamlit 서버 IP: {35.197.92.111}")