"""Weekly performance aggregation."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
import re

import pandas as pd

from services.amount_resolver import resolve_amount, to_millions
from services.sku_resolver import extract_sku_code, normalize_sku, sku_matches_any
from services.time_slotter import assign_slot, inferred_broadcast_date, session_is_disabled, slots_for_date
from services.validator import missing_columns

REQUIRED = ("주문번호", "결제일시", "상품명")
DETAIL_REQUIRED = ("주문번호", "결제일시", "상품명")
RESULT_KEYS = ("final", "summary", "excluded", "duplicates", "errors", "extra_details")
CustomSlots = dict[date, tuple[object, ...]]


def _slot_duration_minutes(slot: object) -> int:
    base = date(2000, 1, 1)
    start_dt = datetime.combine(base, slot.start)
    end_dt = datetime.combine(base, slot.end)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
    return max(1, int((end_dt - start_dt).total_seconds() // 60))
WEARABLE_SKUS = {
    "SM-L340NZEAKOO",
    "SM-L340NZKAKOO",
    "SM-L345NZEAKOO",
    "SM-L345NZKAKOO",
    "SM-L350NZKAKOO",
    "SM-L350NZSAKOO",
    "SM-L355NZKAKOO",
    "SM-L715NZSAKOO",
    "SM-L715NZKAKOO",
}
MOBILE_ACC_SKUS = {
    "EF-CF976CTEGKR",
    "EF-EF976CBEGKR",
    "EF-EF976CGEGKR",
    "EF-EF976CYEGKR",
    "EF-EF976CWEGKR",
    "EF-KF976SBEGKR",
    "EF-KF976SNEGKR",
    "EF-KF976SREGKR",
    "EF-XF976SBEGKR",
    "EF-QF976CTEGKR",
    "EF-UF976CTEGKR",
    "EF-CF971CTEGKR",
    "EF-EF971CBEGKR",
    "EF-EF971CGEGKR",
    "EF-EF971CVEGKR",
    "EF-EF971CWEGKR",
    "EF-KF971SBEGKR",
    "EF-KF971SNEGKR",
    "EF-KF971SREGKR",
    "EF-XF971SBEGKR",
    "EF-QF971CTEGKR",
    "EF-UF971CTEGKR",
    "EF-CF776CTEGKR",
    "EF-EF776CBEGKR",
    "EF-EF776CGEGKR",
    "EF-EF776CVEGKR",
    "EF-EF776CWEGKR",
    "EF-FF776CBEGKR",
    "EF-FF776CSEGKR",
    "EF-QF776CTEGKR",
    "EF-UF776CTEGKR",
    "GP-TOU026PGGBK",
    "GP-TOU026KDBBK",
    "ET-SLL50LBEGKR",
    "ET-SLL50LAEGKR",
    "ET-SLL50LNEGKR",
    "ET-SLL50LUEGKR",
    "ET-SLL50LWEGKR",
    "ET-SNL34SBEGKR",
    "ET-SNL34SGEGKR",
    "ET-SNL34SLEGKR",
    "ET-SNL34SUEGKR",
    "ET-SNL34SYEGKR",
    "ET-SNL35LBEGKR",
    "ET-SNL35LGEGKR",
    "ET-SNL35LLEGKR",
    "ET-SNL35LUEGKR",
    "ET-SNL35LYEGKR",
    "ET-SVL32SDEGKR",
    "ET-SVL32SGEGKR",
    "ET-SVL32SKEGKR",
    "ET-SVL32SLEGKR",
    "ET-SVL32SYEGKR",
    "ET-SVL33LDEGKR",
    "ET-SVL33LGEGKR",
    "ET-SVL33LKEGKR",
    "ET-SVL33LLEGKR",
    "ET-SVL33LYEGKR",
    "ET-SXL34SBEGKR",
    "ET-SXL34SLEGKR",
    "ET-SXL34SMEGKR",
    "ET-SXL34SUEGKR",
    "ET-SXL34SYEGKR",
    "ET-SXL35LBEGKR",
    "ET-SXL35LLEGKR",
    "ET-SXL35LMEGKR",
    "ET-SXL35LUEGKR",
    "ET-SXL35LYEGKR",
    "GP-FPL345KDBTK",
    "GP-FPL355KDBTK",
    "ET-SBL71MAEGKR",
    "ET-SBL71MBEGKR",
    "ET-SBL71MGEGKR",
    "ET-SBL71MJEGKR",
    "ET-SBL71MSEGKR",
    "ET-SNL71MBEGKR",
    "ET-SNL71MDEGKR",
    "ET-SNL71MGEGKR",
    "ET-SNL71MLEGKR",
    "ET-SNL71MOEGKR",
    "ET-SVL70MFEGKR",
    "ET-SVL70MGEGKR",
    "ET-SVL70MJEGKR",
    "ET-SVL70MKEGKR",
    "ET-SVL70MLEGKR",
    "GP-FPL716KDBTK",
}

BASIC_MODEL_SKUS = {
    "워치9 40mm": {"SM-L340", "SM-L345"},
    "워치9 44mm": {"SM-L350", "SM-L355"},
    "울트라2": {"SM-L715"},
}


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
    range_separators = r"[\-~～〜–—－]"
    ranges = re.findall(rf"(\d{{8}})\s*{range_separators}\s*(\d{{8}})", file_name)
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

    singles = re.findall(rf"(?<!{range_separators})\b(\d{{8}})\b(?!\s*{range_separators})", file_name)
    for value in singles:
        dates.add(_parse_yyyymmdd(value))

    return sorted(dates) or None


def _is_live(row: pd.Series) -> bool:
    value = row.get("주문 유입경로")
    if value is not None and not pd.isna(value) and str(value).strip() == "쇼핑라이브":
        return True
    if value is None or pd.isna(value) or not str(value).strip():
        return "원본 구분 열 없음" in str(row.get("쇼핑라이브 판정근거", ""))
    values = list(row.values)
    return any(str(value).strip() == "0" and index + 1 < len(values) and str(values[index + 1]).strip() == "쇼핑라이브" for index, value in enumerate(values))


def _selected_option_code(row: pd.Series) -> str:
    option_code = str(row.get("옵션관리코드", "") or "").strip()
    seller_code = str(row.get("판매자 상품코드", "") or "").strip()
    return (
        extract_sku_code(option_code)
        or extract_sku_code(seller_code)
        or extract_sku_code(row.get("상품명", ""))
        or option_code
        or seller_code
    )


def _normalize_sku(value: object) -> str:
    return normalize_sku(value)


def _digits_only_order_number(value: object) -> str:
    """Return an order number containing digits only, without separators."""
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        numeric = float(value)
        if numeric.is_integer():
            return str(int(numeric))
    text = str(value).strip()
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".", 1)[0]
    return re.sub(r"\D", "", text)


def _matches_detail_schedule(
    payment: pd.Timestamp,
    date_range: tuple[date, date] | None,
    time_range: tuple[time, time] | None,
) -> bool:
    if pd.isna(payment):
        return False
    if date_range is not None:
        start_date, end_date = date_range
        if end_date < start_date:
            start_date, end_date = end_date, start_date
        if not start_date <= payment.date() <= end_date:
            return False
    if time_range is not None:
        start_time, end_time = time_range
        payment_time = payment.time()
        if start_time <= end_time:
            return start_time <= payment_time <= end_time
        return payment_time >= start_time or payment_time <= end_time
    return True


def _matches_optional_sku_filter(row: pd.Series, allowed_skus: set[str] | None) -> bool:
    if not allowed_skus:
        return True
    return sku_matches_any(_selected_option_code(row), allowed_skus)


def _prepare_weekly_source(
    raw_df: pd.DataFrame,
    file_name: str,
    selected_type: str | None,
    allowed_skus: set[str] | None = None,
    custom_slots: CustomSlots | None = None,
) -> tuple[str, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Apply shared weekly/detail inclusion rules and return prepared frames."""
    missing = missing_columns(raw_df, REQUIRED)
    if missing:
        raise ValueError(f"필수 열이 없습니다: {', '.join(missing)}")
    kind = infer_weekly_kind(file_name, selected_type)
    target_dates = sorted(custom_slots) if custom_slots is not None else infer_target_dates(file_name)
    source = raw_df.copy()
    duplicate_mask = source.duplicated(keep="first")
    duplicates = source.loc[duplicate_mask].copy()
    source = source.loc[~duplicate_mask].copy()
    source["_row"] = range(len(source))
    source["_platform"] = source.get("원본몰", pd.Series("네이버", index=source.index)).fillna("미확인").astype(str)
    source["_order_key"] = source["_platform"] + "::" + source["주문번호"].fillna("").astype(str)
    source["_payment"] = pd.to_datetime(source["결제일시"], errors="coerce")
    source["_live"] = source.apply(_is_live, axis=1)
    source["_sku_filter_ok"] = source.apply(lambda row: _matches_optional_sku_filter(row, allowed_skus), axis=1)
    resolved = source.apply(resolve_amount, axis=1)
    source["_amount"] = [item[0] for item in resolved]
    source["_amount_basis"] = [item[1] for item in resolved]
    if "상품주문번호" in source:
        product_duplicate_mask = source["상품주문번호"].notna() & source["상품주문번호"].astype(str).str.strip().ne("") & source.duplicated(
            subset=["_platform", "상품주문번호"], keep="first"
        )
    else:
        duplicate_basis = [column for column in ["_platform", "주문번호", "결제일시", "상품명", "옵션 정보", "_amount"] if column in source]
        product_duplicate_mask = source.duplicated(subset=duplicate_basis, keep="first")
    if product_duplicate_mask.any():
        duplicates = pd.concat([duplicates, source.loc[product_duplicate_mask].copy()], ignore_index=True)
        source = source.loc[~product_duplicate_mask].copy()
    source["_broadcast_date"] = source["_payment"].map(inferred_broadcast_date)
    if custom_slots is not None:
        assignments = source.apply(lambda row: assign_slot(row["_payment"], kind, custom_slots=custom_slots), axis=1)
    else:
        assignments = source.apply(
            lambda row: assign_slot(row["_payment"], kind, row["_broadcast_date"]) if row["_broadcast_date"] else None,
            axis=1,
        )
    if custom_slots is not None:
        source["_broadcast_date"] = [item[0] if item else None for item in assignments]
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
        | ~source["_sku_filter_ok"]
        | source["_slot"].isna()
        | (False if custom_slots is not None else source["_disabled_slot"])
        | ~source["_target_date_ok"]
        | source["_amount"].isna()
    )
    excluded = source.loc[invalid].copy()
    included = source.loc[~invalid].copy()
    errors = source.loc[source["_payment"].isna() | source["_amount"].isna()].copy()
    source.attrs["target_dates"] = target_dates
    source.attrs["custom_slots"] = custom_slots
    return kind, source, included, excluded, duplicates, errors


def process_weekly(
    raw_df: pd.DataFrame,
    file_name: str,
    selected_type: str | None = None,
    allowed_skus: set[str] | None = None,
    custom_slots: CustomSlots | None = None,
) -> dict[str, pd.DataFrame]:
    """Aggregate a weekly raw-order dataframe by broadcast date and slot."""
    kind, source, included, excluded, duplicates, errors = _prepare_weekly_source(raw_df, file_name, selected_type, allowed_skus, custom_slots)
    dates = source.attrs.get("target_dates") or sorted(date_value for date_value in source["_broadcast_date"].dropna().unique())
    rows: list[dict[str, object]] = []
    active_custom_slots = source.attrs.get("custom_slots")
    for broadcast_date in dates:
        for slot in slots_for_date(kind, broadcast_date, active_custom_slots):
            part = included[(included["_broadcast_date"] == broadcast_date) & (included["_slot"] == slot.label)]
            rows.append(
                {
                    "날짜": broadcast_date,
                    "시간": slot.start.strftime("%H:%M"),
                    "duration (분)": _slot_duration_minutes(slot),
                    "수량": int(part["_order_key"].nunique()),
                    "전환율": 0,
                    "금액(백만)": to_millions(part["_amount"].sum()),
                }
            )
    final = pd.DataFrame(rows, columns=["날짜", "시간", "duration (분)", "수량", "전환율", "금액(백만)"])
    return {"final": final, "summary": final.copy(), "excluded": excluded, "duplicates": duplicates, "errors": errors, "extra_details": pd.DataFrame()}


def process_detail(
    raw_df: pd.DataFrame,
    file_name: str,
    selected_type: str | None = None,
    wearable_skus: set[str] | None = None,
    mobile_acc_skus: set[str] | None = None,
    date_range: tuple[date, date] | None = None,
    time_range: tuple[time, time] | None = None,
) -> dict[str, pd.DataFrame]:
    """Create filtered Basic, wearable, and mobile-ACC detail outputs."""
    missing = missing_columns(raw_df, DETAIL_REQUIRED)
    if missing:
        raise ValueError(f"필수 열이 없습니다: {', '.join(missing)}")
    source = raw_df.copy()
    duplicate_mask = source.duplicated(keep="first")
    duplicates = source.loc[duplicate_mask].copy()
    source = source.loc[~duplicate_mask].copy()
    source["_row"] = range(len(source))
    source["_payment"] = pd.to_datetime(source["결제일시"], errors="coerce")
    resolved = source.apply(resolve_amount, axis=1)
    source["_amount"] = [item[0] for item in resolved]
    source["_amount_basis"] = [item[1] for item in resolved]
    source["_selected_option_code"] = source.apply(_selected_option_code, axis=1)
    source["_sku"] = source["_selected_option_code"].map(_normalize_sku)
    active_wearable_skus = {_normalize_sku(value) for value in (wearable_skus or WEARABLE_SKUS) if _normalize_sku(value)}
    active_mobile_acc_skus = {_normalize_sku(value) for value in (mobile_acc_skus or MOBILE_ACC_SKUS) if _normalize_sku(value)}
    source["_wearable_match"] = source["_sku"].map(
        lambda value: sku_matches_any(value, active_wearable_skus)
    )
    source["_mobile_acc_match"] = source["_sku"].map(
        lambda value: sku_matches_any(value, active_mobile_acc_skus)
    )
    source["_basic_model"] = source["_sku"].map(
        lambda value: next(
            (
                model_name
                for model_name, model_skus in BASIC_MODEL_SKUS.items()
                if sku_matches_any(value, model_skus)
            ),
            "",
        )
    )
    source["_schedule_match"] = source["_payment"].map(
        lambda value: _matches_detail_schedule(value, date_range, time_range)
    )

    def build_category_frame(category_name: str, mask: pd.Series) -> pd.DataFrame:
        detail = source.loc[mask].copy()
        if detail.empty:
            return pd.DataFrame(columns=["버전", "결제일시", "주문번호", "상품명", "옵션 관리 코드", "금액"])
        final = detail.assign(
            버전=category_name,
            **{
                "주문번호": detail["주문번호"].map(_digits_only_order_number),
                "옵션 관리 코드": detail["_selected_option_code"],
                "금액": detail["_amount"],
            },
        )
        return final[["버전", "결제일시", "주문번호", "상품명", "옵션 관리 코드", "금액"]].sort_values(
            ["결제일시", "주문번호", "상품명"],
            kind="stable",
        )

    basic_parts = [
        build_category_frame(model_name, source["_basic_model"].eq(model_name) & source["_schedule_match"])
        for model_name in BASIC_MODEL_SKUS
    ]
    basic = pd.concat([frame for frame in basic_parts if not frame.empty], ignore_index=True) if any(
        not frame.empty for frame in basic_parts
    ) else pd.DataFrame(columns=["버전", "결제일시", "주문번호", "상품명", "옵션 관리 코드", "금액"])
    wearable = build_category_frame("웨어러블", source["_wearable_match"] & source["_schedule_match"]).drop(
        columns=["버전"]
    )
    mobile_acc = build_category_frame("모바일 ACC", source["_mobile_acc_match"] & source["_schedule_match"]).drop(
        columns=["버전"]
    )
    category_frames = [frame for frame in (basic, wearable, mobile_acc) if not frame.empty]
    if category_frames:
        final = pd.concat(category_frames, ignore_index=True, sort=False)
    else:
        final = pd.DataFrame(columns=["버전", "결제일시", "주문번호", "상품명", "옵션 관리 코드", "금액"])
    excluded = source.loc[
        (~source["_wearable_match"] & ~source["_mobile_acc_match"] & source["_basic_model"].eq(""))
        | ~source["_schedule_match"]
    ].copy()
    errors = source.loc[source["_payment"].isna()].copy()
    return {
        "final": final,
        "summary": final.copy(),
        "excluded": excluded,
        "duplicates": duplicates,
        "errors": errors,
        "extra_details": pd.DataFrame(),
        "basic": basic,
        "wearable": wearable,
        "mobile_acc": mobile_acc,
    }
