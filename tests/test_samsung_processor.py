import pandas as pd

from processors.samsung_processor import process_samsung


def test_only_sm_and_model_shortening(samsung_frame: pd.DataFrame) -> None:
    result = process_samsung(samsung_frame)
    models = set(result["final"]["모델"]) - {""}
    assert models == {"SM-R390", "SM-L705"}
    assert not any(model.startswith(("EF-", "EP-", "GP-", "EB-", "EI-")) for model in models)


def test_r390_priority_and_multi_model_representative(samsung_frame: pd.DataFrame) -> None:
    result = process_samsung(samsung_frame)
    populated = result["final"][result["final"]["모델"] != ""]
    assert populated.iloc[0]["모델"] == "SM-R390"
    order = result["duplicates"].query("주문번호 == 'S3'").iloc[0]
    assert order["대표 모델"] == "SM-L705"
    assert "복수 SM" in order["처리 기준"]


def test_integrated_and_summary_counts_match(samsung_frame: pd.DataFrame) -> None:
    result = process_samsung(samsung_frame)
    assert result["final"]["실적(대)"].sum() == sum(value for value in result["summary"]["총 주문수"] if value != "")


def test_seller_code_sm_is_used_when_option_code_is_non_sm() -> None:
    frame = pd.DataFrame(
        [["S1", "2026-06-22 01:20", "워치", 1, "EF-CASE", "SM-L320NDAAKOO", 200_000, 0, "쇼핑라이브"]],
        columns=["주문번호", "결제일시", "상품명", "수량", "옵션관리코드", "판매자 상품코드", "상품가격", "옵션가격", "주문 유입경로"],
    )
    result = process_samsung(frame)
    models = set(result["final"]["모델"]) - {""}
    assert models == {"SM-L320"}


def test_samsung_uses_wearable_date_override_slots() -> None:
    frame = pd.DataFrame(
        [["S1", "2026-07-05 20:05", "워치", 1, "SM-R390NZSAKOO", "", 200_000, 0, "쇼핑라이브"]],
        columns=["주문번호", "결제일시", "상품명", "수량", "옵션관리코드", "판매자 상품코드", "상품가격", "옵션가격", "주문 유입경로"],
    )
    result = process_samsung(frame)
    assert "11:40" not in set(result["final"]["시간"])
    assert {"13:00", "20:00", "20:20"}.issubset(set(result["final"]["시간"]))
