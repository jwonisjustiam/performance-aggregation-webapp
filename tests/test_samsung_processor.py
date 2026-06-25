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

