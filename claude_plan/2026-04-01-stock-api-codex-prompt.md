# Codex 任务提示词 — Stock API 实现

## 任务概述

按照以下计划，在本地实现一个 FastAPI 行情服务（stock-api），封装 akshare 数据源，供 stock agent 通过 `web_fetch` 调用 `localhost:7070` 获取 A股/港股实时数据。

---

## 实现计划全文

> 计划文件位于：`docs/superpowers/plans/2026-04-01-stock-api.md`
> 请先读取该文件，以它为权威依据执行所有任务。

---

## 目标目录

所有文件创建在：

```
C:\Users\Administrator\.openclaw\workspace-stock\stock-api\
```

以及修改：

```
C:\Users\Administrator\.openclaw\workspace-stock\TOOLS.md
C:\Users\Administrator\.openclaw\workspace-stock\AGENTS.md
```

---

## 执行规则

1. **严格按计划顺序执行**，Task 1 → Task 2 → … → Task 7，不跳步。
2. **TDD 工作流**：每个模块先写测试（预期失败），再写实现，再确认测试通过，最后提交。
3. **每完成一个 Task 的 Step，立即更新计划文件中对应的 `- [ ]` 为 `- [x]`**，保持进度可追踪。
4. **遇到验证失败时**（如列名不匹配、API 参数变化），以实际运行结果为准修正代码，不要硬编码计划中的示例值。
5. **不要跳过 Task 1 的 akshare 函数验证步骤**，这些步骤是为了确认实际列名，后续 sources.py 依赖这些结果。

---

## 关键约束

- **代理处理**：Clash 已通过 Mixin 规则将国内域名（eastmoney.com、cninfo.com.cn 等）和 127.0.0.0/8 设为 DIRECT，网络层已处理。main.py 和 start.bat 中仍需清除代理环境变量（HTTP_PROXY、HTTPS_PROXY 等）作为双保险，防止 requests 库读取系统代理绕过 Clash 规则。
- **单 worker**：start.bat 必须使用 `--workers 1`，cache.py 使用进程内字典，多 worker 会导致缓存失效。
- **缓存设计**：`/quote` 全市场数据缓存 60s（一次拉取所有股票），`/intraday` 缓存 30s，`/flow`/`/news`/`/announcement` 缓存 60~300s。
- **港股限制**：`/flow` 和 `/announcement` 不支持港股，返回 `{"error": "unsupported_market", ...}`。

---

## 验收标准

完成后需满足：

```bash
# 1. 所有单元测试通过
cd C:\Users\Administrator\.openclaw\workspace-stock\stock-api
pytest tests/ -v
# 预期：全部 PASSED

# 2. 服务正常启动
curl "http://localhost:7070/health"
# 预期：{"status":"ok"}

# 3. A股行情
curl "http://localhost:7070/quote?symbol=600519"
# 预期：返回含 price、name、change_pct 的 JSON

# 4. 港股行情
curl "http://localhost:7070/quote?symbol=00700"
# 预期：返回含 price 的 JSON

# 5. 港股资金流（不支持）
curl "http://localhost:7070/flow?symbol=00700"
# 预期：{"error":"unsupported_market",...}

# 6. A股公告
curl "http://localhost:7070/announcement?symbol=601398"
# 预期：返回 announcements 列表
```

---

## 开始

请先读取计划文件 `docs/superpowers/plans/2026-04-01-stock-api.md`，然后从 **Task 1 Step 1** 开始执行。
