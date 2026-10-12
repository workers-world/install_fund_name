"""HOLDINGS_LIVE_ON_MISS：CACHE_ONLY 下 miss 时按需拉取并写盘。"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class HoldingsLiveOnMissTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmpdir.name)
        (self.data_dir / "fund_holdings").mkdir()
        self.fund_map = {"015692": "某基金"}

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _patch_env(self, **extra: str):
        env = {
            "DATA_DIR": str(self.data_dir),
            "CACHE_ONLY": "1",
            "HOLDINGS_LIVE_ON_MISS": "0",
            **extra,
        }
        return patch.dict(os.environ, env, clear=False)

    def test_cache_miss_raises_without_live_on_miss(self) -> None:
        import holdings
        import lookup

        with self._patch_env(HOLDINGS_LIVE_ON_MISS="0"):
            with (
                patch.object(lookup, "DATA_DIR", self.data_dir),
                patch.object(holdings, "DATA_DIR", self.data_dir),
                patch.object(holdings, "HOLDINGS_DIR", self.data_dir / "fund_holdings"),
                patch.object(holdings, "load_fund_map", return_value=self.fund_map),
                patch.object(holdings, "_cache_enabled", return_value=True),
            ):
                with self.assertRaises(holdings.HoldingsCacheNotFoundError):
                    holdings.fetch_top_holdings("015692")

    def test_cache_miss_live_fetches_and_writes(self) -> None:
        import holdings
        import lookup

        live = {
            "code": "015692",
            "year": "2025",
            "report_period": "2025年1季度股票投资明细",
            "holdings": [
                {
                    "rank": 1,
                    "stock_code": "600519",
                    "stock_name": "贵州茅台",
                    "weight": 8.5,
                    "shares": 1.0,
                    "market_value": 100.0,
                }
            ],
        }
        with self._patch_env(HOLDINGS_LIVE_ON_MISS="1"):
            with (
                patch.object(lookup, "DATA_DIR", self.data_dir),
                patch.object(holdings, "DATA_DIR", self.data_dir),
                patch.object(holdings, "HOLDINGS_DIR", self.data_dir / "fund_holdings"),
                patch.object(holdings, "load_fund_map", return_value=self.fund_map),
                patch.object(holdings, "_cache_enabled", return_value=True),
                patch.object(holdings, "_fetch_live_holdings", return_value=live) as mock_live,
            ):
                result = holdings.fetch_top_holdings("015692")
                self.assertEqual(result["code"], "015692")
                self.assertEqual(len(result["holdings"]), 1)
                mock_live.assert_called_once()
                cache_path = self.data_dir / "fund_holdings" / "015692.json"
                self.assertTrue(cache_path.exists())
                written = json.loads(cache_path.read_text(encoding="utf-8"))
                self.assertEqual(written["holdings"][0]["stock_code"], "600519")

    def test_cache_hit_skips_live(self) -> None:
        import holdings
        import lookup

        cache_path = self.data_dir / "fund_holdings" / "015692.json"
        cached = {
            "code": "015692",
            "year": "2024",
            "report_period": "2024年4季度股票投资明细",
            "holdings": [{"rank": 1, "stock_code": "000001", "stock_name": "平安银行"}],
        }
        cache_path.write_text(json.dumps(cached, ensure_ascii=False), encoding="utf-8")

        with self._patch_env(HOLDINGS_LIVE_ON_MISS="1"):
            with (
                patch.object(lookup, "DATA_DIR", self.data_dir),
                patch.object(holdings, "DATA_DIR", self.data_dir),
                patch.object(holdings, "HOLDINGS_DIR", self.data_dir / "fund_holdings"),
                patch.object(holdings, "load_fund_map", return_value=self.fund_map),
                patch.object(holdings, "_cache_enabled", return_value=True),
                patch.object(holdings, "_fetch_live_holdings") as mock_live,
            ):
                result = holdings.fetch_top_holdings("015692")
                self.assertEqual(result["year"], "2024")
                mock_live.assert_not_called()


if __name__ == "__main__":
    unittest.main()
