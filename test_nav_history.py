"""nav_history 区间切片与涨跌幅（不访问 akshare）。"""

from __future__ import annotations

import unittest
from datetime import date

from nav_history import (
    InvalidFundCodeError,
    InvalidRangeError,
    build_nav_payload,
    clear_nav_cache,
    get_nav_history,
    rows_from_em_frame,
)


def _rows() -> list[dict]:
    return [
        {"date": "2025-12-01", "value": 1.0},
        {"date": "2026-01-02", "value": 1.1},
        {"date": "2026-10-16", "value": 1.2},
    ]


class NavHistoryTests(unittest.TestCase):
    def tearDown(self) -> None:
        clear_nav_cache()

    def test_ytd_slices_from_jan_1(self) -> None:
        payload = build_nav_payload(
            _rows(),
            code="015692",
            range_id="ytd",
            today=date(2026, 10, 16),
        )
        self.assertEqual([p["date"] for p in payload["points"]], ["2026-01-02", "2026-10-16"])
        self.assertAlmostEqual(payload["summary"]["changePct"], 9.0909, places=3)
        self.assertEqual(payload["summary"]["startValue"], 1.1)
        self.assertEqual(payload["unit"], "nav")

    def test_one_month_keeps_recent_point(self) -> None:
        payload = build_nav_payload(
            _rows(),
            code="015692",
            range_id="1m",
            today=date(2026, 10, 16),
        )
        self.assertEqual([p["date"] for p in payload["points"]], ["2026-10-16"])
        self.assertEqual(payload["summary"]["changePct"], 0)

    def test_rejects_bad_code_and_range(self) -> None:
        with self.assertRaises(InvalidFundCodeError):
            get_nav_history("60051", "1y", today=date(2026, 10, 16), fetcher=lambda _c: _rows())
        with self.assertRaises(InvalidRangeError):
            get_nav_history("015692", "2y", today=date(2026, 10, 16), fetcher=lambda _c: _rows())

    def test_cache_skips_second_fetch(self) -> None:
        calls = {"n": 0}

        def fetch(_code: str) -> list[dict]:
            calls["n"] += 1
            return _rows()

        get_nav_history("015692", "1y", today=date(2026, 10, 16), fetcher=fetch, now_sec=1000)
        get_nav_history("015692", "1y", today=date(2026, 10, 16), fetcher=fetch, now_sec=1001)
        self.assertEqual(calls["n"], 1)

    def test_em_frame_columns(self) -> None:
        class Frame:
            columns = ["净值日期", "单位净值", "日增长率"]
            empty = False

            def iterrows(self):
                yield 0, {"净值日期": "2026-10-16", "单位净值": 1.25, "日增长率": 0.1}

        rows = rows_from_em_frame(Frame())
        self.assertEqual(rows, [{"date": "2026-10-16", "value": 1.25}])


if __name__ == "__main__":
    unittest.main()
