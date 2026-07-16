"""标的代码与交易日历 HTTP 服务。"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from holdings import (
    FundNotFoundError,
    HoldingsCacheNotFoundError,
    fetch_top_holdings,
)
from lookup import InstrumentType, lookup_record, normalize_code
from trade_calendar import is_trading_day, normalize_date

app = FastAPI(
    title="标的代码查询服务",
    description="根据 A 股或基金代码查询标的基本信息；支持基金重仓股与 A 股交易日判断",
    version="1.4.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


class ApiResponse(BaseModel):
    code: int = Field(description="业务状态码，0 表示成功")
    message: str = Field(description="状态描述")
    data: dict[str, Any] | None = Field(default=None, description="业务数据")


@app.get("/health", summary="健康检查")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    "/api/v1/instruments/{code}",
    response_model=ApiResponse,
    summary="按代码查询标的信息",
)
def get_instrument(
    code: str,
    type: InstrumentType = Query(
        "stock",
        description="标的类型：stock（A 股）或 fund（基金）",
    ),
) -> ApiResponse:
    try:
        record = lookup_record(code, type)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"上游数据源异常: {exc}") from exc

    if record is None:
        type_label = "A 股" if type == "stock" else "基金"
        raise HTTPException(
            status_code=404,
            detail=f"未找到 {type_label} 代码: {normalize_code(code)}",
        )

    return ApiResponse(code=0, message="success", data=record)


class LookupRequest(BaseModel):
    code: str = Field(description="标的代码，如 600519 或 010736")
    type: InstrumentType = Field(default="stock", description="标的类型")


@app.post(
    "/api/v1/instruments/lookup",
    response_model=ApiResponse,
    summary="按请求体查询标的信息",
)
def lookup_instrument(body: LookupRequest) -> ApiResponse:
    try:
        record = lookup_record(body.code, body.type)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"上游数据源异常: {exc}") from exc

    if record is None:
        type_label = "A 股" if body.type == "stock" else "基金"
        raise HTTPException(
            status_code=404,
            detail=f"未找到 {type_label} 代码: {normalize_code(body.code)}",
        )

    return ApiResponse(code=0, message="success", data=record)


@app.get(
    "/api/v1/funds/{code}/holdings",
    response_model=ApiResponse,
    summary="查询基金前十大重仓股",
)
def get_fund_holdings(
    code: str,
    year: str | None = Query(
        None,
        description="报告年份，如 2024；默认自动尝试当前年与上一年",
    ),
) -> ApiResponse:
    try:
        record = fetch_top_holdings(code, year=year)
    except FundNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except HoldingsCacheNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"上游数据源异常: {exc}") from exc

    return ApiResponse(code=0, message="success", data=record)


@app.get(
    "/api/v1/calendar/trading-day",
    response_model=ApiResponse,
    summary="判断日期是否为 A 股交易日",
)
def get_trading_day(
    date: str = Query(..., description="日期，格式 YYYY-MM-DD"),
) -> ApiResponse:
    try:
        normalize_date(date)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"日期格式非法，需为 YYYY-MM-DD: {date}",
        ) from exc

    try:
        record = is_trading_day(date)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"上游数据源异常: {exc}") from exc

    return ApiResponse(code=0, message="success", data=record)
