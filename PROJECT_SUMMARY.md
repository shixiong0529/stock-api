# Stock API Project Summary

## 1. 项目目标

本项目的目标是：

- 在本机部署一个可供 OpenClaw `stock` agent 调用的本地行情服务
- 使用 `FastAPI` 封装股票数据源
- 为 A 股和港股提供统一的本地 HTTP 接口
- 让 Telegram 中的 `stock` agent 能通过本地服务获取行情、分时、资金流、新闻、公告和市场总览

本地服务地址：

- `http://127.0.0.1:7070`

---

## 2. 已完成开发

项目目录位于：

- `C:\Users\Administrator\.openclaw\workspace-stock\stock-api`

核心文件：

- `main.py`
  - FastAPI 应用入口
  - 暴露 `/health`、`/quote`、`/intraday`、`/flow`、`/news`、`/announcement`、`/get`、`/market/summary`
  - 启动时清理代理环境变量

- `sources.py`
  - 封装个股数据和市场总览数据
  - 统一 A 股、港股代码处理
  - 统一错误返回结构
  - 为 `/market/summary` 实现全市场聚合、指数汇总和快照降级

- `cache.py`
  - 进程内 TTL 缓存

- `start.bat`
  - 使用 `uvicorn` 启动服务
  - 清理代理变量
  - 固定 `--workers 1`

- `tests/`
  - 接口测试
  - 数据源测试
  - 缓存与降级测试

- `market_summary_snapshot.json`
  - 全市场总览的最近一次成功快照
  - 在上游源不可用时作为兜底数据

---

## 3. 已完成接口

当前已完成接口：

- `GET /health`
- `GET /quote?symbol={symbol}`
- `GET /intraday?symbol={symbol}`
- `GET /flow?symbol={symbol}`
- `GET /news?symbol={symbol}`
- `GET /announcement?symbol={symbol}`
- `GET /get?symbol={symbol}`
- `GET /market/summary`

市场支持情况：

- A 股
  - 支持 `/quote`
  - 支持 `/intraday`
  - 支持 `/flow`
  - 支持 `/news`
  - 支持 `/announcement`
  - 支持 `/get`
  - 支持 `/market/summary`

- 港股
  - 支持 `/quote`
  - 支持 `/intraday`
  - 支持 `/news`
  - 不支持 `/flow`
  - 不支持 `/announcement`
  - 不支持 `/get`
  - 当前未纳入 `/market/summary`

港股不支持时统一返回：

```json
{"error":"unsupported_market"}
```

---

## 4. 缓存与运行设计

缓存策略：

- `/quote`
  - 60 秒

- `/intraday`
  - 30 秒

- `/flow`
  - 60 秒

- `/news`
  - 300 秒

- `/announcement`
  - 300 秒

- `/market/summary`
  - 60 秒

运行设计：

- `start.bat` 固定使用 `--workers 1`
- 原因是缓存使用进程内字典，多 worker 会导致缓存不共享

代理处理：

- `main.py` 和 `start.bat` 都会清理：
  - `HTTP_PROXY`
  - `HTTPS_PROXY`
  - `ALL_PROXY`
  - 以及小写版本
- 同时设置：
  - `NO_PROXY=*`
  - `no_proxy=*`

---

## 5. 全市场总览接口

本轮新增并打通的是：

- `GET /market/summary`

返回内容包括：

- `date`
- `breadth`
  - `up_count`
  - `down_count`
  - `flat_count`
  - `total`
- `turnover`
  - `amount`
  - `volume`
- `indices`
  - 上证指数
  - 深证成指
  - 创业板指
  - 沪深300
  - 科创50
- `top_gainers`
  - 全市场涨幅前 5
- `top_losers`
  - 全市场跌幅前 5

支持的用途：

- 让机器人做 A 股收盘总览
- 统计涨跌家数
- 汇总全市场成交额
- 观察关键指数强弱
- 生成市场复盘摘要

---

## 6. 全市场总览的数据源与降级

这部分做过一轮重构。

最开始：

- 使用 `ak.stock_zh_a_spot()`
- 使用 `ak.stock_zh_index_spot_sina()`

问题：

- 上游会出现超时
- 随后又出现返回 HTML、被拦截、被封禁等问题
- 机器人在 8 秒和 20 秒超时下都曾失败

最终处理：

- 个股接口继续保留现有数据源
- `/market/summary` 改为单独实现
- 使用新浪公开行情接口抓取全市场分页数据和关键指数
- 使用并发分页抓取，降低总耗时
- 当上游源不可用时，自动回退到 `market_summary_snapshot.json`

降级字段：

- `stale`
- `stale_reason`

这样即使上游偶发不可用，也不会让机器人继续卡死在超时上。

---

## 7. OpenClaw 接入改动

修改的工作区文档：

- `C:\Users\Administrator\.openclaw\workspace-stock\TOOLS.md`
- `C:\Users\Administrator\.openclaw\workspace-stock\AGENTS.md`

这些规则已经明确：

- 本地 stock-api 地址是 `http://127.0.0.1:7070`
- 不能对 `localhost` 使用 `web_fetch`
- 必须使用 `exec + C:\Windows\System32\curl.exe`
- 个股接口默认 `--max-time 8`
- `/market/summary` 使用更长超时
- 每次查询都必须重新调用本地接口
- 没有当前回合成功的本地 tool result，就不能声称“已验证”

还修改过：

- `C:\Users\Administrator\.openclaw\openclaw.json`

包括：

- `stock` agent 的 exec 策略调整
- Telegram 相关权限更新
- 让机器人更严格地区分“已验证”和“未验证”

---

## 8. 测试与验证结果

自动化测试：

- 当前测试结果：`26 passed`

本地接口验证：

- `/health`
- `/quote?symbol=600519`
- `/quote?symbol=600000`
- `/flow?symbol=600941`
- `/get?symbol=601398`
- `/market/summary`

机器人成功调用记录已确认的包括：

- `GET /quote?symbol=600000`
- `GET /quote?symbol=600519`
- `GET /quote?symbol=601398`
- `GET /flow?symbol=600941`
- `GET /announcement?symbol=600941`
- `GET /market/summary`

`/market/summary` 最近一次成功调用的特点：

- 先调用 `/health`
- 再调用本地 `http://127.0.0.1:7070/market/summary`
- 已拿到完整 JSON
- 不是网页抓取结果，不是猜测

---

## 9. 当前状态

当前项目状态：

- 本地 `stock-api` 已完成开发并运行
- 个股接口已完成并验证
- 全市场总览接口已完成并验证
- 自动化测试已通过
- Telegram `stock` agent 已接入本地接口
- 机器人已经出现真实成功调用记录

---

## 10. 后续可继续扩展

下一步可继续补的方向：

- `/market/sectors`
  - 行业强弱排行
  - 概念强弱排行

- `/market/indices`
  - 更多指数单独输出

- `/market/limitup`
  - 涨停跌停家数
  - 连板统计
  - 炸板率

- 更完整的审计日志
  - 将成功与失败调用单独汇总
