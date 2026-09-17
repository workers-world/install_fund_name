"""A 股交易日历：判断指定日期是否为交易日。"""

from __future__ import annotations

import json
import os
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

import akshare as ak

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))

# trading-days 查询区间跨度上限（约 10 年，366 × 10 含闰年）；超出由 API 层映射 422
MAX_RANGE_DAYS = 3660


def _cache_enabled() -> bool:
    return os.environ.get("CACHE_ONLY", "1").strip().lower() in {"1", "true", "yes"}


def normalize_date(value: str) -> str:
    """标准化为 YYYY-MM-DD；非法格式抛 ValueError。"""
    return date.fromisoformat(value.strip()).isoformat()


@lru_cache(maxsize=1)
def load_trade_dates() -> set[str]:
    cache_path = DATA_DIR / "trade_dates.json"
    if cache_path.exists():
        items = json.loads(cache_path.read_text(encoding="utf-8"))
        return {str(item) for item in items}
    if _cache_enabled():
        raise FileNotFoundError(
            f"缺少缓存文件 {cache_path}，请在宿主机执行: DATA_DIR={DATA_DIR} python scripts/refresh_cache.py"
        )
    df = ak.tool_trade_date_hist_sina()
    return {d.isoformat() for d in df["trade_date"].tolist()}


def is_trading_day(date_str: str) -> dict[str, Any]:
    """判断日期是否为 A 股交易日。"""
    normalized = normalize_date(date_str)
    return {
        "date": normalized,
        "is_trading_day": normalized in load_trade_dates(),
    }


def list_trading_days(start: str, end: str) -> dict[str, Any]:
    """返回 [start, end] 闭区间内的交易日列表（含边界）。

    对数据集聚合（O(数据集大小)）而非逐日推进：天然限界，超长区间不再
    逐日循环烧 CPU，也避免 end=9999-12-31 时 date.fromordinal 越界。
    区间跨度超上限抛 ValueError（API 层映射 422）。
    响应附 dataset_min/dataset_max（数据集覆盖边界），范围外返回空列表。
    """
    start_s = normalize_date(start)
    end_s = normalize_date(end)
    start_d = date.fromisoformat(start_s)
    end_d = date.fromisoformat(end_s)
    if end_d < start_d:
        raise ValueError(f"end 早于 start: {start} > {end}")
    if (end_d - start_d).days > MAX_RANGE_DAYS:
        raise ValueError(
            f"区间跨度超限: {start} ~ {end} 超过 {MAX_RANGE_DAYS} 天（约 10 年），请缩小范围"
        )
    trade = load_trade_dates()
    days = sorted(d for d in trade if start_s <= d <= end_s)
    return {
        "start": start_s,
        "end": end_s,
        "count": len(days),
        "trading_days": days,
        "dataset_min": min(trade, default=None),
        "dataset_max": max(trade, default=None),
    }
