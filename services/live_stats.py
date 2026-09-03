"""Normalize and match Naver Shopping Live statistics to schedule slots."""

from __future__ import annotations

from datetime import date, datetime, time
from io import BytesIO
from pathlib import Path
import re

import pandas as pd


CANONICAL_COLUMNS = [
    "계정",
    "방송 ID",
    "방송 제목",
    "방송일시",
    "라이브중 시청수",
    "유니크 결제자수",
    "결제 상품수",
    "데이터 업데이트 시각",
]

COLUMN_ALIASES = {
    "계정": ("계정", "스토어", "스토어명", "채널", "채널명"),
    "방송 ID": ("방송 ID", "방송ID", "라이브 ID", "라이브ID", "broadcast_id"),
    "방송 제목": ("방송 제목", "방송제목", "라이브 제목", "라이브제목", "title"),
    "방송일시": ("방송일시", "방송 일시", "라이브일시", "라이브 일시", "broadcast_at"),
    "날짜": ("날짜", "방송일", "방송 날짜", "방송날짜", "date"),
    "시간": ("시간", "시작 시간", "시작시간", "방송 시간", "방송시간", "time"),
    "라이브중 시청수": (
        "라이브중 시청수",
        "라이브 중 시청수",
        "시청수",
        "live_viewers",
        "viewer_count",
    ),
    "유니크 결제자수": (
        "유니크 결제자수",
        "결제자수",
        "결제자 수",
        "unique_payers",
        "payer_count",
    ),
    "결제 상품수": ("결제 상품수", "결제상품수", "상품수", "paid_items"),
    "데이터 업데이트 시각": (
        "데이터 업데이트 시각",
        "데이터 업데이트",
        "업데이트 시각",
        "updated_at",
    ),
}


def _clean_column(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _to_number(series: pd.Series) -> pd.Series:
    cleaned = series.astype(str).str.replace(",", "", regex=False).str.extract(r"(-?\d+(?:\.\d+)?)", expand=False)
    return pd.to_numeric(cleaned, errors="coerce")


def normalize_live_stats(raw: pd.DataFrame) -> pd.DataFrame:
    """Return one canonical row per broadcast from CSV/XLSX collector output."""
    if raw is None or raw.empty:
        return pd.DataFrame(columns=CANONICAL_COLUMNS)

    frame = raw.copy()
    frame.columns = [_clean_column(column) for column in frame.columns]
    normalized_lookup = {_clean_column(column).lower(): column for column in frame.columns}
    rename: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            original = normalized_lookup.get(_clean_column(alias).lower())
            if original is not None:
                rename[original] = canonical
                break
    frame = frame.rename(columns=rename)

    if "방송일시" not in frame:
        if "날짜" not in frame or "시간" not in frame:
            raise ValueError("통계 파일에 `방송일시` 또는 `날짜`와 `시간` 열이 필요합니다.")
        frame["방송일시"] = frame["날짜"].astype(str).str.strip() + " " + frame["시간"].astype(str).str.strip()
    if "라이브중 시청수" not in frame:
        raise ValueError("통계 파일에 `라이브중 시청수` 열이 필요합니다.")

    frame["방송일시"] = pd.to_datetime(frame["방송일시"], errors="coerce")
    for column in ("라이브중 시청수", "유니크 결제자수", "결제 상품수"):
        if column not in frame:
            frame[column] = pd.NA
        frame[column] = _to_number(frame[column])
    if "데이터 업데이트 시각" not in frame:
        frame["데이터 업데이트 시각"] = pd.NaT
    else:
        frame["데이터 업데이트 시각"] = pd.to_datetime(frame["데이터 업데이트 시각"], errors="coerce")
    for column in ("계정", "방송 ID", "방송 제목"):
        if column not in frame:
            frame[column] = ""
        frame[column] = frame[column].fillna("").astype(str).str.strip()

    invalid = frame["방송일시"].isna() | frame["라이브중 시청수"].isna()
    if invalid.any():
        raise ValueError(f"통계 파일에 방송일시 또는 라이브중 시청수가 잘못된 행이 {int(invalid.sum())}개 있습니다.")

    frame = frame.sort_values(["방송일시", "데이터 업데이트 시각"], kind="stable")
    dedupe_key = frame["방송 ID"].where(frame["방송 ID"].ne(""), frame["방송일시"].astype(str))
    frame = frame.assign(_dedupe_key=dedupe_key).drop_duplicates("_dedupe_key", keep="last")
    return frame[CANONICAL_COLUMNS].reset_index(drop=True)


def read_live_stats_upload(uploaded_file: object) -> pd.DataFrame:
    """Read a Streamlit-style uploaded CSV/XLSX file and normalize it."""
    name = Path(str(getattr(uploaded_file, "name", "") or "")).name
    suffix = Path(name).suffix.lower()
    payload = uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file.read()
    buffer = BytesIO(payload)
    if suffix == ".csv":
        try:
            raw = pd.read_csv(buffer, encoding="utf-8-sig")
        except UnicodeDecodeError:
            buffer.seek(0)
            raw = pd.read_csv(buffer, encoding="cp949")
    elif suffix in {".xlsx", ".xls"}:
        raw = pd.read_excel(buffer)
    else:
        raise ValueError("통계 파일은 CSV, XLSX 또는 XLS 형식만 지원합니다.")
    return normalize_live_stats(raw)


def match_live_stats(
    stats: pd.DataFrame | None,
    broadcast_date: date,
    slot_start: time,
    tolerance_minutes: int = 15,
) -> pd.Series | None:
    """Match the nearest broadcast start to a configured schedule slot."""
    if stats is None or stats.empty:
        return None
    target = pd.Timestamp(datetime.combine(broadcast_date, slot_start))
    candidates = stats.copy()
    candidates["_distance"] = (pd.to_datetime(candidates["방송일시"]) - target).abs()
    candidates = candidates[candidates["_distance"] <= pd.Timedelta(minutes=tolerance_minutes)]
    if candidates.empty:
        return None
    return candidates.sort_values(["_distance", "데이터 업데이트 시각"], ascending=[True, False], kind="stable").iloc[0]


def conversion_percent(stats_row: pd.Series | None) -> float | None:
    """Calculate unique payer conversion as percentage points."""
    if stats_row is None:
        return None
    viewers = pd.to_numeric(stats_row.get("라이브중 시청수"), errors="coerce")
    payers = pd.to_numeric(stats_row.get("유니크 결제자수"), errors="coerce")
    if pd.isna(viewers) or viewers <= 0 or pd.isna(payers):
        return None
    return float(payers) / float(viewers) * 100


def stats_audit_row(broadcast_date: date, slot_start: time, stats_row: pd.Series | None) -> dict[str, object]:
    """Build an inspectable schedule-to-statistics match record."""
    base: dict[str, object] = {
        "회차 날짜": broadcast_date,
        "회차 시작 시간": slot_start.strftime("%H:%M"),
        "매칭 여부": "미매칭" if stats_row is None else "매칭",
        "방송 ID": "",
        "실제 방송일시": pd.NaT,
        "라이브중 시청수": pd.NA,
        "유니크 결제자수": pd.NA,
        "전환율": pd.NA,
        "데이터 업데이트 시각": pd.NaT,
    }
    if stats_row is None:
        return base
    base.update(
        {
            "방송 ID": stats_row.get("방송 ID", ""),
            "실제 방송일시": stats_row.get("방송일시"),
            "라이브중 시청수": stats_row.get("라이브중 시청수"),
            "유니크 결제자수": stats_row.get("유니크 결제자수"),
            "전환율": conversion_percent(stats_row),
            "데이터 업데이트 시각": stats_row.get("데이터 업데이트 시각"),
        }
    )
    return base
