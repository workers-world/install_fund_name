#!/usr/bin/env python3
"""在宿主机拉取 akshare 全量列表并写入 data/ 缓存（容器内 HTTPS 不可用时使用）。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import akshare as ak

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))


def refresh_stock(path: Path) -> int:
    df = ak.stock_info_a_code_name()
    rows = [
        {"code": str(code).zfill(6), "name": str(name)}
        for code, name in zip(df["code"], df["name"])
    ]
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return len(rows)


def refresh_fund(path: Path) -> int:
    df = ak.fund_name_em()
    rows = [
        {
            "code": str(row["基金代码"]).zfill(6),
            "name": str(row["基金简称"]),
            "fund_type": str(row["基金类型"]),
            "pinyin_abbr": str(row["拼音缩写"]),
            "pinyin_full": str(row["拼音全称"]),
        }
        for _, row in df.iterrows()
    ]
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return len(rows)


def refresh_trade_dates(path: Path) -> int:
    df = ak.tool_trade_date_hist_sina()
    rows = [d.isoformat() for d in df["trade_date"].tolist()]
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return len(rows)


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    stock_path = DATA_DIR / "stock_codes.json"
    fund_path = DATA_DIR / "fund_codes.json"
    trade_dates_path = DATA_DIR / "trade_dates.json"
    try:
        stock_count = refresh_stock(stock_path)
        fund_count = refresh_fund(fund_path)
        trade_count = refresh_trade_dates(trade_dates_path)
    except Exception as exc:
        print(f"刷新失败: {exc}", file=sys.stderr)
        return 1
    print(f"已写入 {stock_path} ({stock_count} 条)")
    print(f"已写入 {fund_path} ({fund_count} 条)")
    print(f"已写入 {trade_dates_path} ({trade_count} 条)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
