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
    """返回 [start, end] 闭区间内的交易日列表（含边界）。"""
    start_d = date.fromisoformat(normalize_date(start))
    end_d = date.fromisoformat(normalize_date(end))
    if end_d < start_d:
        raise ValueError(f"end 早于 start: {start} > {end}")
    trade = load_trade_dates()
    days: list[str] = []
    cur = start_d
    while cur <= end_d:
        iso = cur.isoformat()
        if iso in trade:
            days.append(iso)
        cur = date.fromordinal(cur.toordinal() + 1)
    return {
        "start": start_d.isoformat(),
        "end": end_d.isoformat(),
        "count": len(days),
        "trading_days": days,
    }
