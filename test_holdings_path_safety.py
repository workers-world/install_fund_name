"""持仓缓存路径约束（CodeQL py/path-injection）。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import holdings


class HoldingsPathSafetyTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmpdir.name)
        self.holdings_dir = self.data_dir / "fund_holdings"
        self.holdings_dir.mkdir()

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_valid_code_resolves_under_holdings_dir(self) -> None:
        with (
            patch.object(holdings, "DATA_DIR", self.data_dir),
            patch.object(holdings, "HOLDINGS_DIR", self.holdings_dir),
        ):
            path = holdings._holdings_cache_path("015692")
        self.assertEqual(path, (self.holdings_dir / "015692.json").resolve())
        self.assertTrue(path.is_relative_to(self.holdings_dir.resolve()))

    def test_traversal_code_rejected(self) -> None:
        with (
            patch.object(holdings, "DATA_DIR", self.data_dir),
            patch.object(holdings, "HOLDINGS_DIR", self.holdings_dir),
        ):
            with self.assertRaises(holdings.InvalidHoldingsPathError):
                holdings._holdings_cache_path("../../outside")

    def test_nested_filename_rejected(self) -> None:
        with (
            patch.object(holdings, "DATA_DIR", self.data_dir),
            patch.object(holdings, "HOLDINGS_DIR", self.holdings_dir),
        ):
            with self.assertRaises(holdings.InvalidHoldingsPathError):
                holdings._holdings_cache_path("foo/bar")


if __name__ == "__main__":
    unittest.main()
