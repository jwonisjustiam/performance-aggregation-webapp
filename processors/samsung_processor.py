"""Samsung broadcast performance aggregation."""

from __future__ import annotations

from collections import Counter
from datetime import date

import pandas as pd

from rules.samsung_rules import DEFAULT_BROADCAST_VALUES, SAMSUNG_SLOTS
from services.amount_resolver import resolve_amount
from services.result_formatter import shorten_model
from services.time_slotter import assign_slot, inferred_broadcast_date
from services.validator import missing_columns

REQUIRED = ("주문번호", "결제일시", "상품명", "수량", "상품가격", "옵션가격", "주문 유입경로")


def _target_date(source: pd.DataFrame) -> date:
    inferred = [inferred_broadcast_date(value) for value in source["결제일시"]]
    valid = [value for value in inferred if value is not None]
    if not valid:
        raise ValueError("유효한 결제일 데이터가 없습니다.")
    return Counter(valid).most_common(1)[0][0]


def process_samsung(raw_df: pd.DataFrame, optional_broadcast_df: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
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
    source["_code"] = source.get("옵션관리코드", pd.Series(index=source.index, dtype=object)).fillna("")
    fallback = source.get("판매자 상품코드", pd.Series(index=source.index, dtype=object)).fillna("")
    source["_code"] = source["_code"].where(source["_code"].astype(str).str.strip().ne(""), fallback)
    source["_model"] = source["_code"].map(shorten_model)
    source["_live"] = source["주문 유입경로"].astype(str).str.strip().eq("쇼핑라이브")
    amounts = source.apply(resolve_amount, axis=1)
    source["_amount"] = [item[0] for item in amounts]
    target = _target_date(source)
    assigned = source["_payment"].map(lambda value: assign_slot(value, "wearable", target, SAMSUNG_SLOTS))
    source["_slot"] = [item[1] if item else None for item in assigned]
    source["_date_ok"] = source["_slot"].notna()
    eligible = source["_live"] & source["_model"].str.startswith("SM-") & source["_date_ok"] & source["_amount"].notna()

    verification_rows: list[dict[str, object]] = []
    representative_rows: list[pd.Series] = []
    for order_number, group in source.groupby("주문번호", dropna=False, sort=False):
        valid = group.loc[eligible.loc[group.index]].drop_duplicates(subset=["_model", "상품명", "_amount"], keep="first")
        reason = "정상"
        if valid.empty:
            if not group["_live"].any():
                reason = "쇼핑라이브 없음—제외"
            elif not group["_model"].str.startswith("SM-").any():
                reason = "비-SM 모델—제외"
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
                "쇼핑라이브 SM 원본 행 수": int((group["_live"] & group["_model"].str.startswith("SM-")).sum()),
                "확인된 모델": ", ".join(sorted(set(group.loc[group["_model"].str.startswith("SM-"), "_model"]))),
                "대표 모델": "" if representative is None else representative["_model"],
                "주문 금액": 0 if representative is None else representative["_order_amount"],
                "처리 기준": reason,
            }
        )
    representatives = pd.DataFrame(representative_rows)
    integrated: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    for slot in SAMSUNG_SLOTS:
        part = representatives[representatives["_slot"] == slot.label] if not representatives.empty else representatives
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
