"""Streamlit entry point for the performance aggregation web app."""

from __future__ import annotations

from pathlib import Path
import tempfile

import pandas as pd
import streamlit as st

from processors import process_samsung, process_weekly
from services.excel_reader import XLS_ERROR, read_xlsx
from services.excel_writer import create_result_workbook
from services.validator import input_diagnostics

st.set_page_config(page_title="삼성 라이브 실적 정리 도구", page_icon="📊", layout="wide")
st.title("삼성 라이브 실적 정리 도구")
st.write("Raw Data를 업로드하면 규칙에 따라 실적을 정리하고 결과 파일을 생성합니다.")

with st.expander("사용 안내", expanded=True):
    st.markdown(
        """
        1. **업무 유형**에서 `위클리 실적 취합` 또는 `삼성 실적 취합`을 선택합니다.
        2. 주문 Raw Data를 **1개 이상** 업로드합니다. 여러 파일은 자동으로 합쳐집니다.
        3. 파일 정보와 검사 결과를 확인한 뒤 **분석 시작**을 누릅니다.
        4. 처리 결과를 확인하고 **결과 엑셀 다운로드**를 누릅니다.

        **파일 업로드 전 확인**

        - 위클리 작업에서는 외장하드 파일과 웨어러블 파일을 한 번에 섞지 마세요.
        - 여러 파일에 같은 주문이나 동일한 행이 있어도 중복 제거 규칙을 적용합니다.
        - 암호화 파일은 기본 비밀번호 `1234`, `0000` 순서로만 열기를 시도합니다.
        
        **필수**
        1. 주문 Raw Data는 **결제일** 기준, **전일~당일** 날짜로 주세요.
        2. 파일명은 양식에 맞추어 전달해 주세요.
        - 파일명 양식 예시 : 외장하드_20260625_데이터_1

        """
    )

job_label = st.radio("업무 유형", ["위클리 실적 취합", "삼성 실적 취합"], horizontal=True)
job_type = "weekly" if job_label.startswith("위클리") else "samsung"
uploaded_files = st.file_uploader(
    "주문 Raw Data (.xlsx, 1개 이상)",
    type=None,
    accept_multiple_files=True,
)
broadcast_uploaded = None
if job_type == "samsung":
    broadcast_uploaded = st.file_uploader("방송 실적표 (.xlsx, 선택)", type=None, key="broadcast")
weekly_type = None
if job_type == "weekly":
    weekly_type = st.selectbox("파일명으로 유형을 판정할 수 없을 때 적용할 유형", ["자동 판정", "외장하드", "웨어러블"])

if uploaded_files:
    with tempfile.TemporaryDirectory() as temporary:
        workbooks = []
        file_info_rows = []
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
        payment = pd.to_datetime(frame.get("결제일시"), errors="coerce") if "결제일시" in frame else pd.Series(dtype="datetime64[ns]")
        live = frame.get("주문 유입경로", pd.Series(index=frame.index, dtype=object)).astype(str).str.strip().eq("쇼핑라이브")
        info = {
            "첨부 파일 수": len(uploaded_files),
            "통합 원본 행 수": len(frame),
            "통합 열 수": len(frame.columns),
            "최소 결제일": payment.min(),
            "최대 결제일": payment.max(),
            "쇼핑라이브 행 수": int(live.sum()),
            "쇼핑라이브 고유 주문번호 수": int(frame.loc[live, "주문번호"].nunique()) if "주문번호" in frame else 0,
        }
        st.subheader("파일 기본 정보")
        st.dataframe(pd.DataFrame(file_info_rows), use_container_width=True, hide_index=True)
        st.subheader("통합 원본 정보")
        st.dataframe(pd.DataFrame(info.items(), columns=["항목", "값"]), use_container_width=True, hide_index=True)
        if len(payment.dropna()):
            daily = payment.dt.date.value_counts().sort_index().rename_axis("날짜").reset_index(name="원본 행 수")
            st.dataframe(daily, use_container_width=True, hide_index=True)

        required = ["주문번호", "결제일시", "상품명", "주문 유입경로"]
        diagnostics = input_diagnostics(frame, required)
        st.subheader("파일 검사 결과")
        st.json(diagnostics)

        if st.button("분석 시작", type="primary"):
            try:
                if job_type == "weekly":
                    selected = {"외장하드": "external", "웨어러블": "wearable"}.get(weekly_type)
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
                content, validation = create_result_workbook(job_type, result)
                st.success("분석과 저장 후 재검증을 완료했습니다.")
                st.dataframe(result["final"], use_container_width=True, hide_index=True)
                if not result["extra_details"].empty:
                    st.subheader("외장하드 13:00~14:00 상세")
                    st.dataframe(result["extra_details"], use_container_width=True, hide_index=True)
                st.download_button(
                    "결과 엑셀 다운로드",
                    data=content,
                    file_name=f"{job_type}_result.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                st.caption(f"저장 후 검증: {validation}")
            except Exception as exc:
                st.error(f"처리할 수 없습니다: {exc}")
