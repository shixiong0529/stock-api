# Stock API Interfaces

这份文档用于登记 `stock-api` 当前已经完成的接口，方便后续复查、扩展和回归测试。

记录规则：

- 每新增一个接口，立即补到这里
- 每条记录至少写清楚：接口路径、用途、支持市场、核心返回字段、当前验证状态

---

## 已完成接口

### 1. `GET /health`

- 用途：检查本地 `stock-api` 是否在线
- 支持市场：不区分市场
- 核心返回：
  - `status`
- 示例：

```json
{"status":"ok"}
```

- 当前状态：
  - 已完成
  - 已本地验证

---

### 2. `GET /quote?symbol={symbol}`

- 用途：查询单只股票最新行情
- 支持市场：
  - A 股：支持
  - 港股：支持
- `symbol` 示例：
  - A 股：`600519`、`000001`
  - 港股：`00700`、`00700.HK`
- 核心返回：
  - `symbol`
  - `name`
  - `price`
  - `change_pct`
  - `volume`
  - `pe`
  - `pb`
  - `trading`
- 当前状态：
  - 已完成
  - 已本地验证
  - 已被 Telegram 机器人成功调用

---

### 3. `GET /intraday?symbol={symbol}`

- 用途：查询单只股票盘中走势
- 支持市场：
  - A 股：支持
  - 港股：支持
- 核心返回：
  - `symbol`
  - `data`
  - `fallback`（仅在上游分钟数据失败时出现）
- 说明：
  - 港股分钟接口偶发不稳定时，会回退到快照数据
- 当前状态：
  - 已完成
  - 已本地验证

---

### 4. `GET /flow?symbol={symbol}`

- 用途：查询个股资金流向
- 支持市场：
  - A 股：支持
  - 港股：不支持
- 不支持时返回：

```json
{"error":"unsupported_market"}
```

- 核心返回：
  - `symbol`
  - `date`
  - `main_net`
  - `main_net_pct`
  - `super_large_net`
  - `large_net`
  - `retail_net`
- 当前状态：
  - 已完成
  - 已本地验证
  - 已被 Telegram 机器人成功调用

---

### 5. `GET /news?symbol={symbol}`

- 用途：查询个股相关新闻
- 支持市场：
  - A 股：支持
  - 港股：支持
- 核心返回：
  - `symbol`
  - `news`
- `news` 常见字段：
  - 标题
  - 时间
  - 来源
  - 链接
  - 摘要
- 当前状态：
  - 已完成
  - 已本地实现

---

### 6. `GET /announcement?symbol={symbol}`

- 用途：查询公司公告
- 支持市场：
  - A 股：支持
  - 港股：不支持
- 不支持时返回：

```json
{"error":"unsupported_market"}
```

- 核心返回：
  - `symbol`
  - `announcements`
- 当前状态：
  - 已完成
  - 已本地实现

---

### 7. `GET /get?symbol={symbol}`

- 用途：
  - `GET /announcement` 的短别名
  - 方便在 Telegram 中用更短的命令查公告
- 支持市场：
  - A 股：支持
  - 港股：不支持
- 核心返回：
  - 与 `GET /announcement?symbol={symbol}` 相同
- 当前状态：
  - 已完成
  - 已本地验证

---

### 8. `GET /market/summary`

- 用途：返回 A 股全市场总览，供机器人做收盘复盘、市场概览和情绪判断
- 支持市场：
  - A 股：支持
  - 港股：当前未纳入这条总览接口
- 核心返回：
  - `date`
  - `breadth`
  - `turnover`
  - `indices`
  - `top_gainers`
  - `top_losers`
  - `stale`（仅在上游不可用时出现）
  - `stale_reason`（仅在降级到快照时出现）
- 字段说明：
  - `breadth`
    - `up_count`
    - `down_count`
    - `flat_count`
    - `total`
  - `turnover`
    - `amount`
    - `volume`
  - `indices`
    - 默认收录：上证指数、深证成指、创业板指、沪深300、科创50
  - `top_gainers`
    - 全市场涨幅前 5
  - `top_losers`
    - 全市场跌幅前 5
- 数据实现说明：
  - 使用新浪公开行情接口抓取全市场分页数据与关键指数
  - 上游不可用时回退到最近一次成功快照
- 适用场景：
  - “今天 A 股整体盘面怎么样”
  - “收盘后市场强弱怎么判断”
  - “给我一版全市场复盘摘要”
- 当前状态：
  - 已完成
  - 已测试通过
  - 已加入 API 路由
  - 已被 Telegram 机器人成功调用

---

## 当前未完成接口

- 板块总览
  - 例如行业涨跌幅排行、概念强弱排行、热门板块轮动

- 指数扩展接口
  - 例如更多宽基指数、风格指数、行业指数单独输出

- 市场复盘增强接口
  - 例如封板率、涨停跌停家数、连板统计、炸板率

---

## 更新规则

后续每完成一个接口，请在本文档补充：

1. 接口路径
2. 用途
3. 支持 A 股还是港股
4. 核心返回字段
5. 是否已本地验证
6. 是否已被 Telegram 机器人成功调用
