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
    "pinyin_full": "YIFANGDAHUSHEN300ZHISHUZENGQIANGA",
    "market": "场外",
    "listing_type": null,
    "purchase_status": "开放申购",
    "redeem_status": "开放赎回",
    "min_purchase": 10,
    "daily_limit": 100000000000.0,
    "fee": 0.15,
    "next_open_date": null
  }
}
```

**场内 ETF 示例**

```bash
curl -s "http://127.0.0.1:8000/api/v1/instruments/510300?type=fund"
```

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "code": "510300",
    "name": "华泰柏瑞沪深300ETF",
    "type": "fund",
    "market": "场内",
    "listing_type": "ETF"
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

### 4. 查询基金前十大重仓股

```
GET /api/v1/funds/{code}/holdings?year={year}
```

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `code` | string | 是 | 基金代码 |

**查询参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `year` | string | 否 | 报告年份，如 `2024`；默认自动尝试当前年与上一年 |

**请求示例**

```bash
curl -s "http://127.0.0.1:8000/api/v1/funds/000001/holdings"
```

**成功响应示例**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "code": "000001",
    "year": "2024",
    "report_period": "2024年4季度股票投资明细",
    "holdings": [
      {
        "rank": 1,
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "weight": 8.5,
        "shares": 12.3,
        "market_value": 15000.0
      }
    ]
  }
}
```

**无股票持仓**（货币型、纯债等）：HTTP 200，`holdings` 为空数组。

**未刷持仓缓存**（Docker `CACHE_ONLY=1` 且未开 `HOLDINGS_LIVE_ON_MISS`）：HTTP 404，提示执行 `python scripts/refresh_fund_holdings.py {code}`。

**环境变量**

| 变量 | 默认 | 说明 |
|------|------|------|
| `CACHE_ONLY` | `1` | `1` 时基础表与重仓优先读 `data/`；禁止为补基础表在容器内全量拉 akshare |
| `HOLDINGS_LIVE_ON_MISS` | `0` | 仅影响重仓：`CACHE_ONLY=1` 且 `data/fund_holdings/{code}.json` 缺失时，设为 `1` 则调 akshare 拉取并写盘后返回 200；未开则 404 |

fund-info 生产镜像设 `HOLDINGS_LIVE_ON_MISS=1`，并在周更 CI 预热常用基金池。

宿主机刷持仓缓存：

```bash
source .venv/bin/activate
python scripts/refresh_fund_holdings.py 000001 010736
```

---

### 4.1 查询基金单位净值历史

```
GET /api/v1/funds/{code}/nav-history?range={range}
```

开放式基金「单位净值走势」。`range` 为 `1m`、`3m`、`6m`、`1y`、`ytd`，默认 `1y`。区间按上海日历截取；涨跌幅相对区间内第一个净值点。进程内缓存 15 分钟。代码须为 6 位数字。

```bash
curl -s "http://127.0.0.1:8000/api/v1/funds/015692/nav-history?range=1y"
```

成功时 `data` 含 `code`、`range`、`points`（`date` / `value`）、`summary`（`startDate`、`startValue`、`endDate`、`endValue`、`changePct`）。非法代码或区间 HTTP 422；没有净值点 HTTP 404；上游异常 HTTP 502。

---

### 4.2 反向查询持有某 A 股的基金

```
GET /api/v1/reverse/funds?stock={stock}
```

按 **A 股代码** 查询披露持有该股的基金列表（新浪财经-基金持股）。`stock` 支持 `600519`、`sh600519` 等格式，服务端标准化为 6 位数字。进程内缓存 15 分钟。

```bash
curl -s "http://127.0.0.1:8000/api/v1/reverse/funds?stock=600519"
```

成功时 `data` 含 `stock_code`、`stock_name`、`as_of_date`（结果中最晚截止日期）及 `funds` 数组（`fund_code`、`fund_name`、`weight` 等）。A 股不在本地 `stock_codes.json` 中 HTTP 404；非法代码 HTTP 422；上游异常 HTTP 502。

---

### 5. 判断是否为 A 股交易日

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
| `market` | string | 交易渠道：`场内` / `场外` / `场内+场外` |
| `listing_type` | string \| null | 场内品种：`ETF` / `LOF`；场外为 `null` |
| `purchase_status` | string \| null | 申购状态，如「开放申购」「暂停申购」「限大额」 |
| `redeem_status` | string \| null | 赎回状态，如「开放赎回」「暂停赎回」 |
| `min_purchase` | number \| null | 购买起点（元） |
| `daily_limit` | number \| null | 日累计限定金额（元） |
| `fee` | number \| null | 手续费（单位：%） |
| `next_open_date` | string \| null | 下一开放日（若有） |

业务判断建议：`purchase_status == "开放申购"` 表示可申购；含「暂停」为暂停申购；「限大额」时需结合 `daily_limit`。若名称表有该基金但申购表无，相关字段为 `null`。

`market` / `listing_type` 判定：代码在 ETF 行情列表为 `场内`+`ETF`；在 LOF 列表为 `场内+场外`+`LOF`；其余为 `场外`（`listing_type=null`）。同时出现在两表时优先 ETF。数据优先东财 `fund_etf_spot_em` / `fund_lof_spot_em`，失败时回退新浪 `fund_etf_category_sina`。

### 基金重仓股（`/api/v1/funds/{code}/holdings`）

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | string | 6 位基金代码 |
| `year` | string | 数据来源年份 |
| `report_period` | string \| null | 报告期，如「2024年4季度股票投资明细」 |
| `holdings` | array | 前十大重仓股列表 |

`holdings` 单项：

| 字段 | 类型 | 说明 |
|------|------|------|
| `rank` | int | 排名（1–10） |
| `stock_code` | string | 股票代码 |
| `stock_name` | string | 股票名称 |
| `weight` | number \| null | 占净值比例（%） |
| `shares` | number \| null | 持股数（万股） |
| `market_value` | number \| null | 持仓市值（万元） |

数据为季报披露，非实时；仅股票持仓前十，不含债券持仓。

### 交易日（`/api/v1/calendar/trading-day`）

| 字段 | 类型 | 说明 |
|------|------|------|
| `date` | string | 标准化后的日期 `YYYY-MM-DD` |
| `is_trading_day` | bool | 是否为 A 股交易日 |

---

## 对接注意事项

1. **首次查询较慢**：服务会从 akshare 拉取全量列表并缓存在内存中，同进程内后续查询会快很多。
2. **代码类型需显式指定**：A 股与基金代码均为 6 位数字，无法自动区分，调用方须传正确的 `type`。
3. **Docker 需先刷缓存**：容器默认 `CACHE_ONLY=1`，请在宿主机执行 `python scripts/refresh_cache.py`，生成 `stock_codes.json`、`fund_codes.json`、`fund_purchase.json`、`fund_listing.json`、`trade_dates.json` 后再启动。基金重仓股需按代码单独执行 `python scripts/refresh_fund_holdings.py {code}`，写入 `data/fund_holdings/`。若设 `HOLDINGS_LIVE_ON_MISS=1`，未预热的代码在首次查询时可按需拉取并落盘（仍建议 CI 预热主力池）。
4. **无鉴权**：当前版本未启用认证，部署到公网时请自行加网关或反向代理鉴权。
5. **数据时效**：数据来自第三方公开接口，以 akshare 实际返回为准；交易日日历来自新浪财经，不在历史范围内的日期会判为非交易日；申购状态为天天基金网当日快照；场内/场外依据东财 ETF/LOF 行情列表；重仓股为季报披露数据。

## 变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.7.0 | 2026-10-19 | 新增反向基金查询：`GET /api/v1/reverse/funds` |
| 1.6.0 | 2026-10-19 | 新增基金单位净值历史：`GET /api/v1/funds/{code}/nav-history` |
| 1.5.0 | 2026-10-12 | 重仓支持 `HOLDINGS_LIVE_ON_MISS`：CACHE_ONLY 下 miss 可按需 akshare 写盘 |
| 1.4.0 | 2026-07-16 | 新增基金前十大重仓股：`GET /api/v1/funds/{code}/holdings` |
| 1.3.0 | 2026-07-16 | 基金查询增加场内/场外标识（`market` / `listing_type`） |
| 1.2.0 | 2026-07-16 | 基金查询增加申购/赎回状态等字段（`fund_purchase_em`） |
| 1.1.0 | 2026-07-15 | 新增 A 股交易日查询：`GET /api/v1/calendar/trading-day` |
| 1.0.0 | 2026-07-06 | 初始版本：GET/POST 查询、健康检查 |
