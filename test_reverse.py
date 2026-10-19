"""reverse 反向基金查询（不访问 akshare）。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import app as app_module
from reverse import (
    InvalidStockCodeError,
    StockNotFoundError,
    clear_reverse_cache,
    get_reverse_funds,
    rows_from_sina_frame,
)


class Frame:
    columns = [
        "基金名称",
        "基金代码",
        "持仓数量",
        "占流通股比例",
        "持股市值",
        "占净值比例",
        "截止日期",
    ]
    empty = False

    def iterrows(self):
        yield 0, {
            "基金名称": "招商中证白酒指数C",
            "基金代码": "012414",
            "持仓数量": 4562459,
            "占流通股比例": 0.365,
            "持股市值": 5408750000,
            "占净值比例": 17.28,
            "截止日期": "2026-06-30",
        }


class ReverseTests(unittest.TestCase):
    def tearDown(self) -> None:
        clear_reverse_cache()

    def test_rows_from_sina_frame(self) -> None:
        rows = rows_from_sina_frame(Frame())
        self.assertEqual(rows[0]["fund_code"], "012414")
        self.assertAlmostEqual(rows[0]["weight"], 17.28)

    def test_get_reverse_funds_with_mock(self) -> None:
        stock_map = {"600519": "贵州茅台"}

        def fetch(_code: str) -> Frame:
            return Frame()

        with patch("reverse.load_stock_map", return_value=stock_map):
            payload = get_reverse_funds("600519", fetcher=fetch, now_sec=1000)
        self.assertEqual(payload["stock_code"], "600519")
        self.assertEqual(payload["stock_name"], "贵州茅台")
        self.assertEqual(payload["as_of_date"], "2026-06-30")
        self.assertEqual(len(payload["funds"]), 1)

    def test_cache_skips_second_fetch(self) -> None:
        calls = {"n": 0}
        stock_map = {"600519": "贵州茅台"}

        def fetch(_code: str) -> Frame:
            calls["n"] += 1
            return Frame()

        with patch("reverse.load_stock_map", return_value=stock_map):
            get_reverse_funds("600519", fetcher=fetch, now_sec=1000)
            get_reverse_funds("600519", fetcher=fetch, now_sec=1001)
        self.assertEqual(calls["n"], 1)

    def test_unknown_stock_raises(self) -> None:
        with patch("reverse.load_stock_map", return_value={"600519": "贵州茅台"}):
            with self.assertRaises(StockNotFoundError):
                get_reverse_funds("999999", fetcher=lambda _c: Frame())

    def test_invalid_stock_code(self) -> None:
        with patch("reverse.load_stock_map", return_value={}):
            with self.assertRaises(InvalidStockCodeError):
                get_reverse_funds("600519X", fetcher=lambda _c: Frame())

    def test_routes_registered_on_app(self) -> None:
        paths = app_module.app.openapi()["paths"]
        self.assertIn("/api/v1/reverse/funds", paths)
        self.assertIn("/api/v1/funds/{code}/nav-history", paths)


if __name__ == "__main__":
    unittest.main()
