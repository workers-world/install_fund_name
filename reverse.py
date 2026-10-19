"""按 A 股代码反向查询持有该股的基金（新浪财经-基金持股）。"""

from __future__ import annotations

import time
from typing import Any, Callable

from lookup import _nullable_float, load_stock_map, normalize_code

CACHE_TTL_SEC = 15 * 60

FrameFetcher = Callable[[str], Any]

_cache: dict[str, tuple[float, dict[str, Any]]] = {}


class InvalidStockCodeError(ValueError):
    pass


class StockNotFoundError(LookupError):
    pass


class ReverseUpstreamError(RuntimeError):
    pass


def clear_reverse_cache() -> None:
    _cache.clear()


def normalize_stock_code(code: str) -> str:
    normalized = normalize_code(code)
    if not normalized.isdigit() or len(normalized) != 6:
        raise InvalidStockCodeError(f"A 股代码须为 6 位数字: {code}")
    return normalized


def _as_date_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "nat"}:
        return None
    return text[:10]


def rows_from_sina_frame(frame: Any) -> list[dict[str, Any]]:
    if frame is None or getattr(frame, "empty", True):
        return []
    funds: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        fund_code = normalize_code(str(row["基金代码"]))
        funds.append(
            {
                "fund_code": fund_code,
                "fund_name": str(row["基金名称"]),
                "shares": _nullable_float(row.get("持仓数量")),
                "float_ratio": _nullable_float(row.get("占流通股比例")),
                "market_value": _nullable_float(row.get("持股市值")),
                "weight": _nullable_float(row.get("占净值比例")),
                "as_of_date": _as_date_str(row.get("截止日期")),
            }
        )
    funds.sort(
        key=lambda item: (item.get("weight") is None, -(item.get("weight") or 0)),
    )
    return funds


def build_reverse_payload(stock_code: str, funds: list[dict[str, Any]]) -> dict[str, Any]:
    stock_name = load_stock_map().get(stock_code)
    dates = [item["as_of_date"] for item in funds if item.get("as_of_date")]
    as_of_date = max(dates) if dates else None
    return {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "as_of_date": as_of_date,
        "funds": funds,
    }


def fetch_fund_holders_frame(stock_code: str) -> Any:
    try:
        import akshare as ak
    except Exception as exc:  # noqa: BLE001
        raise ReverseUpstreamError(f"akshare 不可用: {exc}") from exc
    try:
        return ak.stock_fund_stock_holder(symbol=stock_code)
    except Exception as exc:  # noqa: BLE001
        raise ReverseUpstreamError(f"上游数据源异常: {exc}") from exc


def get_reverse_funds(
    stock_code: str,
    *,
    fetcher: FrameFetcher | None = None,
    now_sec: float | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    normalized = normalize_stock_code(stock_code)
    try:
        stock_map = load_stock_map()
    except FileNotFoundError as exc:
        raise ReverseUpstreamError(str(exc)) from exc
    if normalized not in stock_map:
        raise StockNotFoundError(f"未找到 A 股代码: {normalized}")

    stamp = time.time() if now_sec is None else now_sec
    if use_cache:
        cached = _cache.get(normalized)
        if cached and stamp - cached[0] < CACHE_TTL_SEC:
            return cached[1]

    load = fetcher or fetch_fund_holders_frame
    try:
        frame = load(normalized)
    except (InvalidStockCodeError, StockNotFoundError, ReverseUpstreamError):
        raise
    except Exception as exc:  # noqa: BLE001
        raise ReverseUpstreamError(f"上游数据源异常: {exc}") from exc

    funds = rows_from_sina_frame(frame)
    payload = build_reverse_payload(normalized, funds)
    if use_cache:
        _cache[normalized] = (stamp, payload)
    return payload


def register_reverse_routes(app: Any) -> None:
    """把反向基金查询挂到 FastAPI。"""
    from fastapi import HTTPException, Query

    @app.get(
        "/api/v1/reverse/funds",
        summary="按 A 股代码查询持有该股的基金",
    )
    def reverse_funds(
        stock: str = Query(..., description="A 股代码，如 600519"),
    ) -> dict[str, Any]:
        try:
            record = get_reverse_funds(stock)
        except InvalidStockCodeError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except StockNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ReverseUpstreamError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"上游数据源异常: {exc}") from exc
        return {"code": 0, "message": "success", "data": record}
