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


def refresh_fund_purchase(path: Path) -> int:
    df = ak.fund_purchase_em()
    rows = []
    for _, row in df.iterrows():
        rows.append(
            {
                "code": str(row["基金代码"]).zfill(6),
                "name": str(row["基金简称"]),
                "purchase_status": _nullable_str(row.get("申购状态")),
                "redeem_status": _nullable_str(row.get("赎回状态")),
                "min_purchase": _nullable_float(row.get("购买起点")),
                "daily_limit": _nullable_float(row.get("日累计限定金额")),
                "fee": _nullable_float(row.get("手续费")),
                "next_open_date": _nullable_str(row.get("下一开放日")),
            }
        )
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return len(rows)


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


def refresh_fund_listing(path: Path) -> int:
    """缓存场内相关代码：ETF=场内，LOF=场内+场外；同时出现时优先 ETF。"""
    by_code: dict[str, dict[str, str]] = {}

    lof_df = _fetch_listing_df("LOF")
    for _, row in lof_df.iterrows():
        code = _normalize_listing_code(row["代码"])
        by_code[code] = {
            "code": code,
            "name": str(row["名称"]),
            "market": "场内+场外",
            "listing_type": "LOF",
        }

    etf_df = _fetch_listing_df("ETF")
    for _, row in etf_df.iterrows():
        code = _normalize_listing_code(row["代码"])
        by_code[code] = {
            "code": code,
            "name": str(row["名称"]),
            "market": "场内",
            "listing_type": "ETF",
        }

    rows = list(by_code.values())
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return len(rows)


def main() -> int:
    import traceback

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    stock_path = DATA_DIR / "stock_codes.json"
    fund_path = DATA_DIR / "fund_codes.json"
    fund_purchase_path = DATA_DIR / "fund_purchase.json"
    fund_listing_path = DATA_DIR / "fund_listing.json"
    trade_dates_path = DATA_DIR / "trade_dates.json"

    steps = [
        ("stock_codes", refresh_stock, stock_path),
        ("fund_codes", refresh_fund, fund_path),
        ("fund_purchase", refresh_fund_purchase, fund_purchase_path),
        ("fund_listing", refresh_fund_listing, fund_listing_path),
        ("trade_dates", refresh_trade_dates, trade_dates_path),
    ]
    counts: dict[str, int] = {}
    for name, fn, path in steps:
        try:
            print(f"[refresh] 开始: {name}", flush=True)
            counts[name] = fn(path)
            print(f"[refresh] 完成: {name} -> {path} ({counts[name]} 条)", flush=True)
        except Exception as exc:
            print(f"[refresh] 失败步骤: {name}", file=sys.stderr, flush=True)
            print(f"[refresh] 异常类型: {type(exc).__name__}", file=sys.stderr, flush=True)
            print(f"[refresh] 异常信息: {exc!r}", file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            return 1

    print(f"已写入 {stock_path} ({counts['stock_codes']} 条)")
    print(f"已写入 {fund_path} ({counts['fund_codes']} 条)")
    print(f"已写入 {fund_purchase_path} ({counts['fund_purchase']} 条)")
    print(f"已写入 {fund_listing_path} ({counts['fund_listing']} 条)")
    print(f"已写入 {trade_dates_path} ({counts['trade_dates']} 条)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
