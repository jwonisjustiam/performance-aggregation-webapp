"""Samsung broadcast performance aggregation."""

from __future__ import annotations

from collections import Counter
from datetime import date

import pandas as pd

from processors.weekly_processor import infer_target_dates
from rules.samsung_rules import DEFAULT_BROADCAST_VALUES
from services.amount_resolver import resolve_amount
from services.result_formatter import shorten_model
from services.time_slotter import assign_slot, inferred_broadcast_date, session_is_disabled, slots_for_date
from services.validator import missing_columns

REQUIRED = ("주문번호", "결제일시", "상품명", "수량", "상품가격", "옵션가격", "주문 유입경로")
DEFAULT_MODEL_PREFIXES = ("SM-",)
CustomSlots = dict[date, tuple[object, ...]]


def _select_model_code(row: pd.Series) -> str:
    option_code = str(row.get("옵션관리코드", "") or "").strip().upper()
    seller_code = str(row.get("판매자 상품코드", "") or "").strip().upper()
    if option_code.startswith("SM"):
        return option_code
    if seller_code.startswith("SM"):
        return seller_code
    return option_code or seller_code


def _target_date(source: pd.DataFrame) -> date:
    inferred = [inferred_broadcast_date(value) for value in source["결제일시"]]
    valid = [value for value in inferred if value is not None]
    if not valid:
        raise ValueError("유효한 결제일 데이터가 없습니다.")
    return Counter(valid).most_common(1)[0][0]


def process_samsung(
    raw_df: pd.DataFrame,
    file_name: str = "",
    optional_broadcast_df: pd.DataFrame | None = None,
    model_prefixes: tuple[str, ...] | None = None,
    custom_slots: CustomSlots | None = None,
) -> dict[str, pd.DataFrame]:
    """Aggregate Samsung SM orders into the three required result sheets."""
    missing = missing_columns(raw_df, REQUIRED)
    if missing:
        raise ValueError(f"필수 열이 없습니다: {', '.join(missing)}")
    if not any(column in raw_df for column in ("옵션관리코드", "판매자 상품코드")):
        raise ValueError("옵션관리코드 또는 판매자 상품코드 열이 필요합니다.")
    source = raw_df.copy()
    source["_source_row"] = range(len(source))
    exact_duplicates = source.duplicated(keep="first")
    source = source.loc[~exact_duplicates].copy()
    source["_payment"] = pd.to_datetime(source["결제일시"], errors="coerce")
    source["_code"] = source.apply(_select_model_code, axis=1)
    source["_model"] = source["_code"].map(shorten_model)
    active_prefixes = tuple(prefix.strip().upper() for prefix in (model_prefixes or DEFAULT_MODEL_PREFIXES) if prefix.strip())
    if not active_prefixes:
        active_prefixes = DEFAULT_MODEL_PREFIXES
    source["_target_model"] = source["_model"].str.startswith(active_prefixes)
    source["_live"] = source["주문 유입경로"].astype(str).str.strip().eq("쇼핑라이브")
    amounts = source.apply(resolve_amount, axis=1)
    source["_amount"] = [item[0] for item in amounts]
    target_dates = infer_target_dates(file_name)
    fallback_target = _target_date(source)
    source["_broadcast_date"] = source["_payment"].map(inferred_broadcast_date)
    if custom_slots:
        assigned = source.apply(lambda row: assign_slot(row["_payment"], "wearable", custom_slots=custom_slots), axis=1)
    else:
        assigned = source.apply(
            lambda row: assign_slot(row["_payment"], "wearable", row["_broadcast_date"]) if row["_broadcast_date"] else None,
            axis=1,
        )
    if custom_slots:
        source["_broadcast_date"] = [item[0] if item else None for item in assigned]
    source["_slot"] = [item[1] if item else None for item in assigned]
    source["_target_date_ok"] = True if target_dates is None else source["_broadcast_date"].isin(target_dates)
    source["_disabled_slot"] = source.apply(
        lambda row: session_is_disabled("wearable", row["_broadcast_date"], row["_slot"]) if row["_broadcast_date"] else False,
        axis=1,
    )
    source["_date_ok"] = source["_slot"].notna() & source["_target_date_ok"] & (True if custom_slots else ~source["_disabled_slot"])
    eligible = source["_live"] & source["_target_model"] & source["_date_ok"] & source["_amount"].notna()

    verification_rows: list[dict[str, object]] = []
    representative_rows: list[pd.Series] = []
    for order_number, group in source.groupby("주문번호", dropna=False, sort=False):
        valid = group.loc[eligible.loc[group.index]].drop_duplicates(subset=["_model", "상품명", "_amount"], keep="first")
        reason = "정상"
        if valid.empty:
            if not group["_live"].any():
                reason = "쇼핑라이브 없음—제외"
            elif not group["_target_model"].any():
                reason = "대상 모델 규칙 밖—제외"
            elif not group["_target_date_ok"].any():
                reason = "작업 날짜 범위 밖—제외"
            elif not group["_date_ok"].any():
                reason = "회차 범위 밖—제외"
            else:
                reason = "옵션관리코드 없음—제외"
            representative = None
        else:
            representative = valid.sort_values(["_amount", "_source_row"], ascending=[False, True], kind="stable").iloc[0].copy()
            representative["_order_amount"] = float(valid["_amount"].sum())
            representative_rows.append(representative)
            if valid["_model"].nunique() > 1:
                reason = "복수 SM 모델 주문—최고 금액 모델 대표"
            elif len(group) > len(valid):
                reason = "동일 상품 중복 행 제거"
        verification_rows.append(
            {
                "주문번호": order_number,
                "결제일시": group["_payment"].min(),
                "쇼핑라이브 SM 원본 행 수": int((group["_live"] & group["_target_model"]).sum()),
                "확인된 모델": ", ".join(sorted(set(group.loc[group["_target_model"], "_model"]))),
                "대표 모델": "" if representative is None else representative["_model"],
                "주문 금액": 0 if representative is None else representative["_order_amount"],
                "처리 기준": reason,
            }
        )
    representatives = pd.DataFrame(representative_rows)
    integrated: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    output_dates = target_dates or sorted(source.loc[source["_date_ok"], "_broadcast_date"].dropna().unique()) or [fallback_target]
    for target in output_dates:
        for slot in slots_for_date("wearable", target, custom_slots):
            if not representatives.empty:
                part = representatives[(representatives["_broadcast_date"] == target) & (representatives["_slot"] == slot.label)]
            else:
                part = representatives
            counts = part.groupby("_model")["주문번호"].nunique().to_dict() if not part.empty else {}
            models = sorted(counts, key=lambda model: (model != "SM-R390", model)) or [""]
            for model in models:
                integrated.append(
                    {
                        "월": target.month,
                        "일": target.day,
                        "요일": "월화수목금토일"[target.weekday()],
                        **DEFAULT_BROADCAST_VALUES,
                        "시간": slot.label,
                        "모델": model,
                        "실적(대)": int(counts.get(model, 0)),
                    }
                )
            summary_rows.append(
                {
                    "월": target.month,
                    "일": target.day,
                    "요일": "월화수목금토일"[target.weekday()],
                    "시간": slot.label,
                    "총 주문수": "" if part.empty else int(part["주문번호"].nunique()),
                    "총 금액": "" if part.empty else float(part["_order_amount"].sum()),
                }
            )
    final_columns = ["월", "일", "요일", "플랫폼", "제작 주체", "시간", "Duration (분)", "담당/SOP", "View(만)", "모델", "실적(대)"]
    final = pd.DataFrame(integrated)[final_columns]
    summary = pd.DataFrame(summary_rows)
    duplicates = pd.DataFrame(verification_rows)
    excluded = source.loc[~eligible].copy()
    errors = source.loc[source["_payment"].isna() | source["_amount"].isna()].copy()
    return {"final": final, "summary": summary, "excluded": excluded, "duplicates": duplicates, "errors": errors, "extra_details": pd.DataFrame()}
