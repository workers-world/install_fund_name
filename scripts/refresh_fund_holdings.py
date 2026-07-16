#!/usr/bin/env python3
"""在宿主机拉取单只或多只基金持仓并写入 data/fund_holdings/ 缓存。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 宿主机直连 akshare，写入缓存供 Docker CACHE_ONLY=1 读取
os.environ.setdefault("CACHE_ONLY", "0")
os.environ.setdefault("DATA_DIR", str(Path(__file__).resolve().parent.parent / "data"))

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from holdings import fetch_top_holdings, normalize_code  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print(
            "用法: python scripts/refresh_fund_holdings.py CODE [CODE...]",
            file=sys.stderr,
        )
        return 1

    failed = False
    for raw_code in sys.argv[1:]:
        code = normalize_code(raw_code)
        try:
            result = fetch_top_holdings(code)
            count = len(result.get("holdings", []))
            period = result.get("report_period") or "无股票持仓"
            print(f"已写入 {code}: {count} 条持仓, 报告期 {period}")
        except Exception as exc:
            print(f"{code} 刷新失败: {exc}", file=sys.stderr)
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
