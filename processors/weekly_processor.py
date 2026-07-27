"""Weekly performance aggregation."""

from __future__ import annotations

from datetime import date, timedelta
import re

import pandas as pd

from services.amount_resolver import resolve_amount, to_millions
from services.time_slotter import assign_slot, inferred_broadcast_date, session_is_disabled, slots_for_date
from services.validator import missing_columns

REQUIRED = ("주문번호", "결제일시", "상품명", "주문 유입경로")
RESULT_KEYS = ("final", "summary", "excluded", "duplicates", "errors", "extra_details")


def infer_weekly_kind(file_name: str, selected_type: str | None = None) -> str:
    has_external = "외장하드" in file_name
    has_wearable = "웨어러블" in file_name
    if has_external and has_wearable:
        raise ValueError("외장하드와 웨어러블 Raw Data를 한 번에 혼합할 수 없습니다. 업무 유형별로 나누어 처리해주세요.")
    if has_external:
        return "external"
    if has_wearable:
        return "wearable"
    if selected_type in {"external", "wearable"}:
        return selected_type
    raise ValueError("파일명에서 유형을 확인할 수 없습니다. 외장하드 또는 웨어러블 유형을 선택해주세요.")


def _parse_yyyymmdd(value: str) -> date:
    return date(int(value[:4]), int(value[4:6]), int(value[6:8]))


def infer_target_dates(file_name: str) -> list[date] | None:
    """Infer requested broadcast dates from file names such as 20260710~20260712."""
    ranges = re.findall(r"(\d{8})\s*[~-]\s*(\d{8})", file_name)
    dates: set[date] = set()
    for start_text, end_text in ranges:
        start = _parse_yyyymmdd(start_text)
        end = _parse_yyyymmdd(end_text)
        if end < start:
            start, end = end, start
        current = start
        while current <= end:
            dates.add(current)
            current += timedelta(days=1)

    singles = re.findall(r"(?<![~-])\b(\d{8})\b(?!\s*[~-])", file_name)
    for value in singles:
        dates.add(_parse_yyyymmdd(value))

    return sorted(dates) or None


def _is_live(row: pd.Series) -> bool:
    if str(row.get("주문 유입경로", "")).strip() == "쇼핑라이브":
        return True
    values = list(row.values)
    return any(str(value).strip() == "0" and index + 1 < len(values) and str(values[index + 1]).strip() == "쇼핑라이브" for index, value in enumerate(values))


def _selected_option_code(row: pd.Series) -> str:
    option_code = str(row.get("옵션관리코드", "") or "").strip()
    seller_code = str(row.get("판매자 상품코드", "") or "").strip()
    return option_code or seller_code


def _prepare_weekly_source(
    raw_df: pd.DataFrame,
    file_name: str,
    selected_type: str | None,
) -> tuple[str, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Apply shared weekly/detail inclusion rules and return prepared frames."""
    missing = missing_columns(raw_df, REQUIRED)
    if missing:
        raise ValueError(f"필수 열이 없습니다: {', '.join(missing)}")
    kind = infer_weekly_kind(file_name, selected_type)
    target_dates = infer_target_dates(file_name)
    source = raw_df.copy()
    duplicate_mask = source.duplicated(keep="first")
    duplicates = source.loc[duplicate_mask].copy()
    source = source.loc[~duplicate_mask].copy()
    source["_row"] = range(len(source))
    source["_payment"] = pd.to_datetime(source["결제일시"], errors="coerce")
    source["_live"] = source.apply(_is_live, axis=1)
    resolved = source.apply(resolve_amount, axis=1)
    source["_amount"] = [item[0] for item in resolved]
    source["_amount_basis"] = [item[1] for item in resolved]
    if "상품주문번호" in source:
        product_duplicate_mask = source["상품주문번호"].notna() & source["상품주문번호"].astype(str).str.strip().ne("") & source.duplicated(
            subset=["상품주문번호"], keep="first"
        )
    else:
        duplicate_basis = [column for column in ["주문번호", "결제일시", "상품명", "옵션 정보", "_amount"] if column in source]
        product_duplicate_mask = source.duplicated(subset=duplicate_basis, keep="first")
    if product_duplicate_mask.any():
        duplicates = pd.concat([duplicates, source.loc[product_duplicate_mask].copy()], ignore_index=True)
        source = source.loc[~product_duplicate_mask].copy()
    source["_broadcast_date"] = source["_payment"].map(inferred_broadcast_date)
    assignments = source.apply(
        lambda row: assign_slot(row["_payment"], kind, row["_broadcast_date"]) if row["_broadcast_date"] else None,
        axis=1,
    )
    source["_slot"] = [item[1] if item else None for item in assignments]
    source["_disabled_slot"] = source.apply(
        lambda row: session_is_disabled(kind, row["_broadcast_date"], row["_slot"]) if row["_broadcast_date"] else False,
        axis=1,
    )
    source["_target_date_ok"] = True if target_dates is None else source["_broadcast_date"].isin(target_dates)
    invalid_order = source["주문번호"].isna() | source["주문번호"].astype(str).str.strip().eq("")
    invalid = (
        invalid_order
        | source["_payment"].isna()
        | ~source["_live"]
        | source["_slot"].isna()
        | source["_disabled_slot"]
        | ~source["_target_date_ok"]
        | source["_amount"].isna()
    )
    excluded = source.loc[invalid].copy()
    included = source.loc[~invalid].copy()
    errors = source.loc[source["_payment"].isna() | source["_amount"].isna()].copy()
    source.attrs["target_dates"] = target_dates
    return kind, source, included, excluded, duplicates, errors


def process_weekly(raw_df: pd.DataFrame, file_name: str, selected_type: str | None = None) -> dict[str, pd.DataFrame]:
    """Aggregate a weekly raw-order dataframe by broadcast date and slot."""
    kind, source, included, excluded, duplicates, errors = _prepare_weekly_source(raw_df, file_name, selected_type)
    dates = source.attrs.get("target_dates") or sorted(date_value for date_value in source["_broadcast_date"].dropna().unique())
    rows: list[dict[str, object]] = []
    for broadcast_date in dates:
        for slot in slots_for_date(kind, broadcast_date):
            part = included[(included["_broadcast_date"] == broadcast_date) & (included["_slot"] == slot.label)]
            rows.append(
                {
                    "날짜": broadcast_date,
                    "시간": slot.label,
                    "수량": int(part["주문번호"].nunique()),
                    "전환율": 0,
                    "금액(백만)": to_millions(part["_amount"].sum()),
                }
            )
    final = pd.DataFrame(rows, columns=["날짜", "시간", "수량", "전환율", "금액(백만)"])
    return {"final": final, "summary": final.copy(), "excluded": excluded, "duplicates": duplicates, "errors": errors, "extra_details": pd.DataFrame()}


def process_detail(raw_df: pd.DataFrame, file_name: str, selected_type: str | None = None) -> dict[str, pd.DataFrame]:
    """Create a detail-level output using the same inclusion rules as weekly aggregation."""
    _, _, included, excluded, duplicates, errors = _prepare_weekly_source(raw_df, file_name, selected_type)
    detail = included.copy()
    if detail.empty:
        final = pd.DataFrame(columns=["날짜", "시간", "주문번호", "상품명", "옵션 관리 코드", "금액"])
    else:
        detail["_selected_option_code"] = detail.apply(_selected_option_code, axis=1)
        final = detail.assign(
            날짜=detail["_broadcast_date"],
            시간=detail["_slot"],
            **{
                "옵션 관리 코드": detail["_selected_option_code"],
                "금액": detail["_amount"],
            },
        )
        final = final[["날짜", "시간", "주문번호", "상품명", "옵션 관리 코드", "금액"]].sort_values(
            ["날짜", "시간", "주문번호", "상품명"],
            kind="stable",
        )
    return {"final": final, "summary": final.copy(), "excluded": excluded, "duplicates": duplicates, "errors": errors, "extra_details": pd.DataFrame()}
