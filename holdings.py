"""基金前十大重仓股查询。"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import akshare as ak

from lookup import DATA_DIR, _cache_enabled, _nullable_float, load_fund_map, normalize_code

HOLDINGS_DIR = DATA_DIR / "fund_holdings"


class FundNotFoundError(ValueError):
    """基金代码不在名称表中。"""


class HoldingsCacheNotFoundError(FileNotFoundError):
    """持仓缓存文件不存在。"""


def _holdings_cache_path(code: str) -> Path:
    return HOLDINGS_DIR / f"{normalize_code(code)}.json"


def _parse_quarter_key(period: str) -> tuple[int, int]:
    """解析「2024年4季度股票投资明细」→ (2024, 4)。"""
    match = re.search(r"(\d{4})年(\d)季度", str(period))
    if match:
        return int(match.group(1)), int(match.group(2))
    return 0, 0


def _normalize_stock_code(raw: object) -> str:
    text = str(raw).strip()
    if text.startswith(("sh", "sz", "SH", "SZ")):
        text = text[2:]
    return text.zfill(6)


def _fetch_holdings_from_api(code: str, year: str) -> dict[str, Any]:
    df = ak.fund_portfolio_hold_em(symbol=code, date=year)
    normalized = normalize_code(code)

    if df.empty or "季度" not in df.columns:
        return {
            "code": normalized,
            "year": year,
            "report_period": None,
            "holdings": [],
        }

    latest_period = max(df["季度"].astype(str).unique(), key=_parse_quarter_key)
    quarter_df = df[df["季度"].astype(str) == latest_period].copy()
    quarter_df = quarter_df.sort_values("占净值比例", ascending=False).head(10)

    holdings: list[dict[str, Any]] = []
    for rank, (_, row) in enumerate(quarter_df.iterrows(), start=1):
        holdings.append(
            {
                "rank": rank,
                "stock_code": _normalize_stock_code(row["股票代码"]),
                "stock_name": str(row["股票名称"]),
                "weight": _nullable_float(row.get("占净值比例")),
                "shares": _nullable_float(row.get("持股数")),
                "market_value": _nullable_float(row.get("持仓市值")),
            }
        )

    return {
        "code": normalized,
        "year": year,
        "report_period": latest_period,
        "holdings": holdings,
    }


def _fetch_live_holdings(code: str, year: str | None = None) -> dict[str, Any]:
    normalized = normalize_code(code)
    if year:
        years = [year]
    else:
        current_year = datetime.now().year
        years = [str(current_year), str(current_year - 1)]

    best: dict[str, Any] | None = None
    last_error: Exception | None = None
    for y in years:
        try:
            data = _fetch_holdings_from_api(normalized, y)
        except Exception as exc:
            last_error = exc
            continue
        if data["holdings"]:
            return data
        if best is None or data.get("report_period"):
            best = data

    if best is not None:
        return best
    if last_error is not None:
        raise last_error
    return {
        "code": normalized,
        "year": years[0],
        "report_period": None,
        "holdings": [],
    }


def _write_holdings_cache(data: dict[str, Any]) -> None:
    HOLDINGS_DIR.mkdir(parents=True, exist_ok=True)
    path = _holdings_cache_path(data["code"])
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def fetch_top_holdings(code: str, year: str | None = None) -> dict[str, Any]:
    """查询基金最新报告期前十大重仓股；CACHE_ONLY 时只读本地缓存。"""
    normalized = normalize_code(code)
    if normalized not in load_fund_map():
        raise FundNotFoundError(f"未找到基金代码: {normalized}")

    if _cache_enabled():
        cache_path = _holdings_cache_path(normalized)
        if not cache_path.exists():
            raise HoldingsCacheNotFoundError(
                f"缺少持仓缓存 {cache_path}，请在宿主机执行: "
                f"DATA_DIR={DATA_DIR} python scripts/refresh_fund_holdings.py {normalized}"
            )
        return json.loads(cache_path.read_text(encoding="utf-8"))

    data = _fetch_live_holdings(normalized, year)
    _write_holdings_cache(data)
    return data
