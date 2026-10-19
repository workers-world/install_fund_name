"""基金单位净值历史（akshare 开放式基金「单位净值走势」）。

区间相对上海日历：1m/3m/6m/1y 为最近 N 个自然日，ytd 为当年 1 月 1 日起。
涨跌幅相对区间内第一个净值点（与 Admin Baseline 基准一致）。
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")

RANGE_DAYS = {"1m": 31, "3m": 92, "6m": 183, "1y": 366}
CACHE_TTL_SEC = 15 * 60

RowFetcher = Callable[[str], list[dict[str, Any]]]

_cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}


class InvalidFundCodeError(ValueError):
    pass


class InvalidRangeError(ValueError):
    pass


class FundNavNotFoundError(LookupError):
    pass


class FundNavUpstreamError(RuntimeError):
    pass


def clear_nav_cache() -> None:
    _cache.clear()


def shanghai_today(now: datetime | None = None) -> date:
    moment = now or datetime.now(SHANGHAI)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=SHANGHAI)
    return moment.astimezone(SHANGHAI).date()


def normalize_fund_code(code: str) -> str:
    raw = (code or "").strip()
    if not raw.isdigit() or len(raw) != 6:
        raise InvalidFundCodeError(f"基金代码须为 6 位数字: {code}")
    return raw


def range_window(range_id: str, today: date) -> tuple[date, date]:
    if range_id == "ytd":
        return date(today.year, 1, 1), today
    days = RANGE_DAYS.get(range_id)
    if days is None:
        raise InvalidRangeError(f"range 非法: {range_id}")
    return today - timedelta(days=days), today


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()[:10]
    return date.fromisoformat(text)


def build_nav_payload(
    rows: list[dict[str, Any]],
    *,
    code: str,
    range_id: str,
    today: date,
    name: str | None = None,
) -> dict[str, Any]:
    start, end = range_window(range_id, today)
    points: list[dict[str, Any]] = []
    for row in rows:
        day = _as_date(row["date"])
        if day < start or day > end:
            continue
        value = float(row["value"])
        if value <= 0:
            continue
        points.append({"date": day.isoformat(), "value": round(value, 6)})
    points.sort(key=lambda item: item["date"])
    if not points:
        raise FundNavNotFoundError(f"区间内无净值: {code}")
    first = points[0]
    last = points[-1]
    change = (last["value"] - first["value"]) / first["value"] * 100
    return {
        "code": code,
        "name": name,
        "range": range_id,
        "unit": "nav",
        "points": points,
        "summary": {
            "startDate": first["date"],
            "endDate": last["date"],
            "startValue": first["value"],
            "endValue": last["value"],
            "changePct": round(change, 4),
        },
    }


def rows_from_em_frame(frame: Any) -> list[dict[str, Any]]:
    """akshare fund_open_fund_info_em(indicator=单位净值走势) → 统一行。"""
    if frame is None or getattr(frame, "empty", True):
        return []
    date_col = "净值日期" if "净值日期" in frame.columns else frame.columns[0]
    value_col = "单位净值" if "单位净值" in frame.columns else frame.columns[1]
    rows: list[dict[str, Any]] = []
    for _, item in frame.iterrows():
        rows.append({"date": item[date_col], "value": item[value_col]})
    return rows


def fetch_open_fund_nav_rows(code: str) -> list[dict[str, Any]]:
    try:
        import akshare as ak
    except Exception as exc:  # noqa: BLE001
        raise FundNavUpstreamError(f"akshare 不可用: {exc}") from exc
    try:
        frame = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
    except Exception as exc:  # noqa: BLE001
        raise FundNavUpstreamError(f"上游数据源异常: {exc}") from exc
    rows = rows_from_em_frame(frame)
    if not rows:
        raise FundNavNotFoundError(f"未找到基金净值: {code}")
    return rows


def get_nav_history(
    code: str,
    range_id: str = "1y",
    *,
    today: date | None = None,
    fetcher: RowFetcher | None = None,
    now_sec: float | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    normalized = normalize_fund_code(code)
    if range_id not in RANGE_DAYS and range_id != "ytd":
        raise InvalidRangeError(f"range 非法: {range_id}")
    clock = today or shanghai_today()
    stamp = time.time() if now_sec is None else now_sec
    key = (normalized, range_id)
    if use_cache:
        cached = _cache.get(key)
        if cached and stamp - cached[0] < CACHE_TTL_SEC:
            return cached[1]
    load = fetcher or fetch_open_fund_nav_rows
    try:
        rows = load(normalized)
    except (FundNavNotFoundError, FundNavUpstreamError, InvalidFundCodeError, InvalidRangeError):
        raise
    except Exception as exc:  # noqa: BLE001
        raise FundNavUpstreamError(f"上游数据源异常: {exc}") from exc
    payload = build_nav_payload(rows, code=normalized, range_id=range_id, today=clock)
    if use_cache:
        _cache[key] = (stamp, payload)
    return payload


def register_nav_history_routes(app: Any) -> None:
    """把净值历史挂到 FastAPI。install_fund_name 与 fund-info 覆盖版 app 共用这一处。"""
    from fastapi import HTTPException, Query

    @app.get(
        "/api/v1/funds/{code}/nav-history",
        summary="查询基金单位净值历史",
    )
    def get_fund_nav_history(
        code: str,
        range_id: str = Query("1y", alias="range", description="1m | 3m | 6m | 1y | ytd"),
    ) -> dict[str, Any]:
        try:
            record = get_nav_history(code, range_id)
        except (InvalidFundCodeError, InvalidRangeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except FundNavNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except FundNavUpstreamError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"上游数据源异常: {exc}") from exc
        return {"code": 0, "message": "success", "data": record}
