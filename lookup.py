#!/usr/bin/env python3
"""按标的代码查询 A 股或基金基本信息。"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import akshare as ak

InstrumentType = Literal["stock", "fund"]
DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))


def normalize_code(code: str) -> str:
    """标准化代码：去 sh/sz 前缀，补齐 6 位。"""
    cleaned = re.sub(r"^(sh|sz)", "", code.strip().lower())
    return cleaned.zfill(6)


def _cache_enabled() -> bool:
    return os.environ.get("CACHE_ONLY", "1").strip().lower() in {"1", "true", "yes"}


@lru_cache(maxsize=1)
def load_stock_map() -> dict[str, str]:
    cache_path = DATA_DIR / "stock_codes.json"
    if cache_path.exists():
        items = json.loads(cache_path.read_text(encoding="utf-8"))
        return {item["code"]: item["name"] for item in items}
    if _cache_enabled():
        raise FileNotFoundError(
            f"缺少缓存文件 {cache_path}，请在宿主机执行: DATA_DIR={DATA_DIR} python scripts/refresh_cache.py"
        )
    df = ak.stock_info_a_code_name()
    return {str(code).zfill(6): str(name) for code, name in zip(df["code"], df["name"])}


@lru_cache(maxsize=1)
def load_fund_map() -> dict[str, dict[str, str]]:
    cache_path = DATA_DIR / "fund_codes.json"
    if cache_path.exists():
        items = json.loads(cache_path.read_text(encoding="utf-8"))
        return {item["code"]: item for item in items}
    if _cache_enabled():
        raise FileNotFoundError(
            f"缺少缓存文件 {cache_path}，请在宿主机执行: DATA_DIR={DATA_DIR} python scripts/refresh_cache.py"
        )
    df = ak.fund_name_em()
    result: dict[str, dict[str, str]] = {}
    for _, row in df.iterrows():
        code = str(row["基金代码"]).zfill(6)
        result[code] = {
            "code": code,
            "name": str(row["基金简称"]),
            "fund_type": str(row["基金类型"]),
            "pinyin_abbr": str(row["拼音缩写"]),
            "pinyin_full": str(row["拼音全称"]),
        }
    return result


def lookup_record(code: str, instrument_type: InstrumentType) -> dict[str, Any] | None:
    """查询单条标的信息，返回统一 JSON 结构；未找到返回 None。"""
    normalized = normalize_code(code)

    if instrument_type == "stock":
        name = load_stock_map().get(normalized)
        if not name:
            return None
        return {
            "code": normalized,
            "name": name,
            "type": "stock",
        }

    fund = load_fund_map().get(normalized)
    if not fund:
        return None
    return {
        "code": normalized,
        "name": fund["name"],
        "type": "fund",
        "fund_type": fund.get("fund_type", ""),
        "pinyin_abbr": fund.get("pinyin_abbr", ""),
        "pinyin_full": fund.get("pinyin_full", ""),
    }


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
        record = lookup_record(args.code, args.type)
    except Exception as exc:
        print(f"查询失败: {exc}", file=sys.stderr)
        return 1

    if record is None:
        type_label = "A 股" if args.type == "stock" else "基金"
        print(f"未找到 {type_label} 代码: {normalize_code(args.code)}", file=sys.stderr)
        return 1

    for key, value in record.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
