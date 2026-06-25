"""Weekly performance aggregation."""

from __future__ import annotations

from datetime import date

import pandas as pd

from services.amount_resolver import resolve_amount, to_millions
from services.time_slotter import assign_slot, inferred_broadcast_date, slots_for_date
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


def _is_live(row: pd.Series) -> bool:
    if str(row.get("주문 유입경로", "")).strip() == "쇼핑라이브":
        return True
    values = list(row.values)
    return any(str(value).strip() == "0" and index + 1 < len(values) and str(values[index + 1]).strip() == "쇼핑라이브" for index, value in enumerate(values))


def process_weekly(raw_df: pd.DataFrame, file_name: str, selected_type: str | None = None) -> dict[str, pd.DataFrame]:
    """Aggregate a weekly raw-order dataframe by broadcast date and slot."""
    missing = missing_columns(raw_df, REQUIRED)
    if missing:
        raise ValueError(f"필수 열이 없습니다: {', '.join(missing)}")
    kind = infer_weekly_kind(file_name, selected_type)
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
    source["_broadcast_date"] = source["_payment"].map(inferred_broadcast_date)
    assignments = source.apply(
        lambda row: assign_slot(row["_payment"], kind, row["_broadcast_date"]) if row["_broadcast_date"] else None,
        axis=1,
    )
    source["_slot"] = [item[1] if item else None for item in assignments]
    invalid_order = source["주문번호"].isna() | source["주문번호"].astype(str).str.strip().eq("")
    invalid = invalid_order | source["_payment"].isna() | ~source["_live"] | source["_slot"].isna() | source["_amount"].isna()
    excluded = source.loc[invalid].copy()
    included = source.loc[~invalid].copy()

    dates = sorted(date_value for date_value in source["_broadcast_date"].dropna().unique())
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
    extra = included[(included["_slot"] == "13:00~14:00") & (kind == "external")].copy()
    if not extra.empty:
        extra = extra.assign(
            **{
                "반영 금액": extra["_amount"],
                "금액 기준": extra["_amount_basis"],
                "해당 회차 합계": extra.groupby(["_broadcast_date", "_slot"])["_amount"].transform("sum"),
            }
        )
        keep = [column for column in ["주문번호", "결제일시", "상품명", "옵션 정보", "반영 금액", "금액 기준", "해당 회차 합계"] if column in extra]
        extra = extra[keep]
    errors = source.loc[source["_payment"].isna() | source["_amount"].isna()].copy()
    return {"final": final, "summary": final.copy(), "excluded": excluded, "duplicates": duplicates, "errors": errors, "extra_details": extra}
