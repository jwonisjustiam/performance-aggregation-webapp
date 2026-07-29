"""Generate deterministic sample workbooks for local testing."""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    weekly = pd.DataFrame(
        [
            ["W1", "2026-06-22 13:00", "외장하드", 1, 1000000, 0, "쇼핑라이브", "", ""],
            ["W1", "2026-06-22 13:00", "추가상품", 1, 500000, 0, "쇼핑라이브", "", ""],
            ["W2", "2026-06-23 00:30", "자정주문", 1, 0, 0, "쇼핑라이브", "", ""],
            ["W3", "invalid", "날짜오류", "x", "bad", 0, "쇼핑라이브", "", ""],
            ["W4", "2026-06-22 14:00", "비라이브", 1, 1000, 0, "검색", "", ""],
            ["W5", "2026-06-22 12:00", "열밀림", 1, 1000, 0, 0, "쇼핑라이브", ""],
        ],
        columns=["주문번호", "결제일시", "상품명", "수량", "상품가격", "옵션가격", "주문 유입경로", "밀린열", "옵션 정보"],
    )
    weekly = pd.concat([weekly, weekly.iloc[[0]]], ignore_index=True)
    samsung = pd.DataFrame(
        [
            ["S1", "2026-06-22 01:20", "워치", 1, "SM-R390NZSAKOO", "", 200000, 0, "쇼핑라이브"],
            ["S2", "2026-06-22 03:30", "폰", 1, "EF-CASE", "", 30000, 0, "쇼핑라이브"],
            ["S3", "2026-06-22 09:40", "모델A", 1, "SM-L320NDAAKOO", "", 300000, 0, "쇼핑라이브"],
            ["S3", "2026-06-22 09:40", "모델B", 1, "SM-L705NAW1KOO", "", 400000, 0, "쇼핑라이브"],
            ["S4", "2026-06-22 11:50", "코드없음", 1, "", "", 10000, 0, "쇼핑라이브"],
            ["S5", "2026-06-22 13:55", "검색주문", 1, "SM-R390NZSAKOO", "", 200000, 0, "검색"],
        ],
        columns=["주문번호", "결제일시", "상품명", "수량", "옵션관리코드", "판매자 상품코드", "상품가격", "옵션가격", "주문 유입경로"],
    )
    for folder in (ROOT / "samples" / "weekly", ROOT / "samples" / "samsung"):
        folder.mkdir(parents=True, exist_ok=True)
    weekly.to_excel(ROOT / "samples" / "weekly" / "외장하드 샘플.xlsx", index=False)
    samsung.to_excel(ROOT / "samples" / "samsung" / "삼성 샘플.xlsx", index=False)
    print("sample workbooks generated")


if __name__ == "__main__":
    main()

