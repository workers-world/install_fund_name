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


def _nullable_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "nat"}:
        return None
    return text


def _nullable_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return number


@lru_cache(maxsize=1)
def load_fund_purchase_map() -> dict[str, dict[str, Any]]:
    cache_path = DATA_DIR / "fund_purchase.json"
    if cache_path.exists():
        items = json.loads(cache_path.read_text(encoding="utf-8"))
        return {item["code"]: item for item in items}
    if _cache_enabled():
        raise FileNotFoundError(
            f"缺少缓存文件 {cache_path}，请在宿主机执行: DATA_DIR={DATA_DIR} python scripts/refresh_cache.py"
        )
    df = ak.fund_purchase_em()
    result: dict[str, dict[str, Any]] = {}
    for _, row in df.iterrows():
        code = str(row["基金代码"]).zfill(6)
        result[code] = {
            "code": code,
            "name": str(row["基金简称"]),
            "purchase_status": _nullable_str(row.get("申购状态")),
            "redeem_status": _nullable_str(row.get("赎回状态")),
            "min_purchase": _nullable_float(row.get("购买起点")),
            "daily_limit": _nullable_float(row.get("日累计限定金额")),
            "fee": _nullable_float(row.get("手续费")),
            "next_open_date": _nullable_str(row.get("下一开放日")),
        }
    return result


def _normalize_listing_code(raw: object) -> str:
    text = str(raw).strip().lower()
    if text.startswith(("sh", "sz")):
        text = text[2:]
    return text.zfill(6)


def _fetch_listing_df(listing_type: str):
    """优先东财行情，失败时回退新浪分类列表。"""
    if listing_type == "ETF":
        try:
            return ak.fund_etf_spot_em()
        except Exception:
            return ak.fund_etf_category_sina(symbol="ETF基金")
    try:
        return ak.fund_lof_spot_em()
    except Exception:
        return ak.fund_etf_category_sina(symbol="LOF基金")


def _build_fund_listing_map() -> dict[str, dict[str, Any]]:
    """从 ETF/LOF 行情接口拼装场内列表；同时出现时优先 ETF。"""
    result: dict[str, dict[str, Any]] = {}

    lof_df = _fetch_listing_df("LOF")
    for _, row in lof_df.iterrows():
        code = _normalize_listing_code(row["代码"])
        result[code] = {
            "code": code,
            "name": str(row["名称"]),
            "market": "场内+场外",
            "listing_type": "LOF",
        }

    etf_df = _fetch_listing_df("ETF")
    for _, row in etf_df.iterrows():
        code = _normalize_listing_code(row["代码"])
        result[code] = {
            "code": code,
            "name": str(row["名称"]),
            "market": "场内",
            "listing_type": "ETF",
        }
    return result


@lru_cache(maxsize=1)
def load_fund_listing_map() -> dict[str, dict[str, Any]]:
    cache_path = DATA_DIR / "fund_listing.json"
    if cache_path.exists():
        items = json.loads(cache_path.read_text(encoding="utf-8"))
        return {item["code"]: item for item in items}
    if _cache_enabled():
        raise FileNotFoundError(
            f"缺少缓存文件 {cache_path}，请在宿主机执行: DATA_DIR={DATA_DIR} python scripts/refresh_cache.py"
        )
    return _build_fund_listing_map()


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

    purchase = load_fund_purchase_map().get(normalized)
    listing = load_fund_listing_map().get(normalized)
    return {
        "code": normalized,
        "name": fund["name"],
        "type": "fund",
        "fund_type": fund.get("fund_type", ""),
        "pinyin_abbr": fund.get("pinyin_abbr", ""),
        "pinyin_full": fund.get("pinyin_full", ""),
        "market": listing["market"] if listing else "场外",
        "listing_type": listing["listing_type"] if listing else None,
        "purchase_status": purchase.get("purchase_status") if purchase else None,
        "redeem_status": purchase.get("redeem_status") if purchase else None,
        "min_purchase": purchase.get("min_purchase") if purchase else None,
        "daily_limit": purchase.get("daily_limit") if purchase else None,
        "fee": purchase.get("fee") if purchase else None,
        "next_open_date": purchase.get("next_open_date") if purchase else None,
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
