#!/usr/bin/env python3
"""按标的代码查询 A 股或基金基本信息。"""

from __future__ import annotations

import argparse
import re
import sys
from functools import lru_cache

import akshare as ak
import pandas as pd


def normalize_code(code: str) -> str:
    """标准化代码：去 sh/sz 前缀，补齐 6 位。"""
    cleaned = re.sub(r"^(sh|sz)", "", code.strip().lower())
    return cleaned.zfill(6)


@lru_cache(maxsize=1)
def load_stock_table() -> pd.DataFrame:
    df = ak.stock_info_a_code_name()
    df = df.copy()
    df["code"] = df["code"].astype(str).str.zfill(6)
    return df


@lru_cache(maxsize=1)
def load_fund_table() -> pd.DataFrame:
    df = ak.fund_name_em()
    df = df.copy()
    df["基金代码"] = df["基金代码"].astype(str).str.zfill(6)
    return df


def lookup(code: str, instrument_type: str) -> pd.DataFrame:
    normalized = normalize_code(code)

    if instrument_type == "stock":
        df = load_stock_table()
        result = df[df["code"] == normalized]
    elif instrument_type == "fund":
        df = load_fund_table()
        result = df[df["基金代码"] == normalized]
    else:
        raise ValueError(f"不支持的类型: {instrument_type}")

    return result.reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="按标的代码查询 A 股或基金基本信息")
    parser.add_argument("code", help="标的代码，如 600519 或 010736")
    parser.add_argument(
        "--type",
        choices=["stock", "fund"],
        default="stock",
        help="标的类型：stock（A 股）或 fund（基金），默认 stock",
    )
    args = parser.parse_args()

    try:
        result = lookup(args.code, args.type)
    except Exception as exc:
        print(f"查询失败: {exc}", file=sys.stderr)
        return 1

    if result.empty:
        type_label = "A 股" if args.type == "stock" else "基金"
        print(f"未找到 {type_label} 代码: {normalize_code(args.code)}", file=sys.stderr)
        return 1

    print(result.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
