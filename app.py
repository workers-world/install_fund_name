"""标的代码查询 HTTP 服务。"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from lookup import InstrumentType, lookup_record, normalize_code

app = FastAPI(
    title="标的代码查询服务",
    description="根据 A 股或基金代码查询标的基本信息",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


class ApiResponse(BaseModel):
    code: int = Field(description="业务状态码，0 表示成功")
    message: str = Field(description="状态描述")
    data: dict[str, Any] | None = Field(default=None, description="标的信息")


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
