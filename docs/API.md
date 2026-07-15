# 标的代码查询服务 — 对接文档

## 概述

本服务提供 HTTP 接口，根据 **A 股** 或 **公募基金** 代码查询标的基本信息，并支持判断指定日期是否为 **A 股交易日**。数据来源于 akshare（东方财富 / 新浪财经）。

| 项目 | 说明 |
|------|------|
| 默认地址 | `http://127.0.0.1:8000` |
| 协议 | HTTP/1.1 |
| 数据格式 | JSON |
| 字符编码 | UTF-8 |
| API 版本 | v1 |

## 启动服务

### Docker Compose（推荐）

```bash
cd install_fund_name
docker compose up -d --build
```

常用命令：

```bash
docker compose ps          # 查看状态
docker compose logs -f api # 查看日志
docker compose down        # 停止并移除容器
```

### 本地开发

```bash
cd install_fund_name
source .venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
uvicorn app:app --host 0.0.0.0 --port 8000
```

启动后可访问：

- Swagger UI：`http://127.0.0.1:8000/docs`
- ReDoc：`http://127.0.0.1:8000/redoc`
- OpenAPI JSON：`http://127.0.0.1:8000/openapi.json`

## 通用约定

### 请求头

| Header | 值 | 必填 |
|--------|-----|------|
| `Accept` | `application/json` | 否 |
| `Content-Type` | `application/json` | POST 必填 |

### 成功响应结构

```json
{
  "code": 0,
  "message": "success",
  "data": { }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | int | 业务状态码，`0` 表示成功 |
| `message` | string | 状态描述 |
| `data` | object | 业务数据，结构见下文 |

### 错误响应结构

HTTP 状态码非 2xx 时，响应体为 FastAPI 标准错误格式：

```json
{
  "detail": "错误描述"
}
```

| HTTP 状态码 | 场景 |
|-------------|------|
| 404 | 代码不存在 |
| 422 | 参数校验失败（如 type 非法、日期格式非法） |
| 502 | 上游数据源（akshare）异常或缺少本地缓存 |

### 标的类型 `type`

| 值 | 含义 |
|----|------|
| `stock` | A 股（默认） |
| `fund` | 公募基金 |

代码支持 `600519`、`sh600519`、`SZ000001` 等格式，服务端会标准化为 6 位数字。

---

## 接口列表

### 1. 健康检查

```
GET /health
```

**响应示例**

```json
{
  "status": "ok"
}
```

---

### 2. 按路径参数查询（推荐）

```
GET /api/v1/instruments/{code}?type={type}
```

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `code` | string | 是 | 标的代码 |

**查询参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `type` | string | 否 | `stock` | `stock` 或 `fund` |

**A 股查询示例**

```bash
curl -s "http://127.0.0.1:8000/api/v1/instruments/600519?type=stock"
```

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "code": "600519",
    "name": "贵州茅台",
    "type": "stock"
  }
}
```

**基金查询示例**

```bash
curl -s "http://127.0.0.1:8000/api/v1/instruments/010736?type=fund"
```

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "code": "010736",
    "name": "易方达沪深300指数增强A",
    "type": "fund",
    "fund_type": "指数型-股票",
    "pinyin_abbr": "YFDHS300ZSZQA",
    "pinyin_full": "YIFANGDAHUSHEN300ZHISHUZENGQIANGA"
  }
}
```

**未找到示例**

```bash
curl -s "http://127.0.0.1:8000/api/v1/instruments/999999?type=stock"
```

HTTP 404：

```json
{
  "detail": "未找到 A 股 代码: 999999"
}
```

---

### 3. 按请求体查询

```
POST /api/v1/instruments/lookup
Content-Type: application/json
```

**请求体**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `code` | string | 是 | — | 标的代码 |
| `type` | string | 否 | `stock` | `stock` 或 `fund` |

**请求示例**

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/instruments/lookup" \
  -H "Content-Type: application/json" \
  -d '{"code": "010736", "type": "fund"}'
```

**响应**：与 GET 接口相同。

---

### 4. 判断是否为 A 股交易日

```
GET /api/v1/calendar/trading-day?date={date}
```

**查询参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `date` | string | 是 | 日期，格式 `YYYY-MM-DD` |

**交易日示例**

```bash
curl -s "http://127.0.0.1:8000/api/v1/calendar/trading-day?date=2026-07-15"
```

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "date": "2026-07-15",
    "is_trading_day": true
  }
}
```

**非交易日示例**（周末 / 节假日等仍返回 HTTP 200）

```bash
curl -s "http://127.0.0.1:8000/api/v1/calendar/trading-day?date=2026-07-11"
```

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "date": "2026-07-11",
    "is_trading_day": false
  }
}
```

**日期格式非法**

```bash
curl -s "http://127.0.0.1:8000/api/v1/calendar/trading-day?date=2026/07/15"
```

HTTP 422：

```json
{
  "detail": "日期格式非法，需为 YYYY-MM-DD: 2026/07/15"
}
```

---

## 响应字段说明

### A 股（`type=stock`）

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | string | 6 位股票代码 |
| `name` | string | 股票简称 |
| `type` | string | 固定为 `stock` |

### 基金（`type=fund`）

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | string | 6 位基金代码 |
| `name` | string | 基金简称 |
| `type` | string | 固定为 `fund` |
| `fund_type` | string | 基金类型，如「混合型」 |
| `pinyin_abbr` | string | 拼音缩写 |
| `pinyin_full` | string | 拼音全称 |

### 交易日（`/api/v1/calendar/trading-day`）

| 字段 | 类型 | 说明 |
|------|------|------|
| `date` | string | 标准化后的日期 `YYYY-MM-DD` |
| `is_trading_day` | bool | 是否为 A 股交易日 |

---

## 对接注意事项

1. **首次查询较慢**：服务会从 akshare 拉取全量列表并缓存在内存中，同进程内后续查询会快很多。
2. **代码类型需显式指定**：A 股与基金代码均为 6 位数字，无法自动区分，调用方须传正确的 `type`。
3. **Docker 需先刷缓存**：容器默认 `CACHE_ONLY=1`，请在宿主机执行 `python scripts/refresh_cache.py`，生成 `stock_codes.json`、`fund_codes.json`、`trade_dates.json` 后再启动。
4. **无鉴权**：当前版本未启用认证，部署到公网时请自行加网关或反向代理鉴权。
5. **数据时效**：数据来自第三方公开接口，以 akshare 实际返回为准；交易日日历来自新浪财经，不在历史范围内的日期会判为非交易日。

## 变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.1.0 | 2026-07-15 | 新增 A 股交易日查询：`GET /api/v1/calendar/trading-day` |
| 1.0.0 | 2026-07-06 | 初始版本：GET/POST 查询、健康检查 |
