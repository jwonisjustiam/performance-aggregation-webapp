from datetime import date, time

import pandas as pd
import pytest

from services.live_stats import conversion_percent, match_live_stats, normalize_live_stats


def test_normalize_aliases_and_match_nearest_schedule_time() -> None:
    raw = pd.DataFrame(
        [
            {
                "스토어명": "삼성공식파트너 쇼마젠시",
                "라이브ID": "2014040",
                "방송 날짜": "2026-09-02",
                "방송 시간": "23:08",
                "시청수": "52 뷰",
                "결제자수": "2 명",
                "결제상품수": "3 개",
                "업데이트 시각": "2026-09-03 10:00:00",
            }
        ]
    )

    stats = normalize_live_stats(raw)
    matched = match_live_stats(stats, date(2026, 9, 2), time(23, 10))

    assert matched is not None
    assert matched["방송 ID"] == "2014040"
    assert matched["라이브중 시청수"] == 52
    assert conversion_percent(matched) == pytest.approx(2 / 52 * 100)


def test_zero_viewers_leave_conversion_blank() -> None:
    stats = normalize_live_stats(
        pd.DataFrame([{"방송일시": "2026-09-02 23:08", "라이브중 시청수": 0, "유니크 결제자수": 2}])
    )
    matched = match_live_stats(stats, date(2026, 9, 2), time(23, 10))
    assert conversion_percent(matched) is None


def test_invalid_stats_require_broadcast_time() -> None:
    with pytest.raises(ValueError, match="방송일시"):
        normalize_live_stats(pd.DataFrame([{"라이브중 시청수": 10}]))
