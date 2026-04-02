# stock-api

`stock-api` 是一个运行在本机的股票数据服务，使用 `FastAPI` 对外提供 HTTP 接口，供 OpenClaw 的 `stock` agent 通过本地地址 `http://127.0.0.1:7070` 获取 A 股、港股和 A 股全市场总览数据。

这个项目的定位是“本机行情中间层”：

- 把上游数据源封装成稳定的本地接口
- 统一个股和市场总览的返回格式
- 让机器人优先调用本地 `stock-api`
- 降低机器人直接拼公网网页数据的依赖

---

## 1. 项目介绍

当前已经完成的能力：

- 个股实时行情
- 个股盘中分时
- 个股资金流向
- 个股相关新闻
- 个股公告
- 公告短命令别名
- A 股全市场总览

当前主要接口：

- `GET /health`
- `GET /quote?symbol={symbol}`
- `GET /intraday?symbol={symbol}`
- `GET /flow?symbol={symbol}`
- `GET /news?symbol={symbol}`
- `GET /announcement?symbol={symbol}`
- `GET /get?symbol={symbol}`
- `GET /market/summary`

更多细节见：

- `INTERFACES.md`
- `PROJECT_SUMMARY.md`

---

## 2. 目录结构

项目目录建议理解为：

- `<OPENCLAW_HOME>\workspace-stock\stock-api`

常见占位说明：

- `<OPENCLAW_HOME>`
  - 指本机 OpenClaw 根目录
  - 例如 `C:\Users\<YOUR_USER>\.openclaw`

- `<WORKSPACE_ROOT>`
  - 指工作区根目录
  - 例如 `<OPENCLAW_HOME>\workspace-stock`

核心文件：

- `main.py`
  - FastAPI 路由入口

- `sources.py`
  - 数据源封装与聚合逻辑

- `cache.py`
  - 进程内 TTL 缓存

- `start.bat`
  - 本地启动脚本

- `requirements.txt`
  - Python 依赖

- `market_summary_snapshot.json`
  - 全市场总览快照兜底文件

- `tests/`
  - 自动化测试

---

## 3. 运行环境

建议环境：

- Windows
- Python 3.11+
- 可正常访问本机 OpenClaw 工作区

依赖安装：

```powershell
cd <OPENCLAW_HOME>\workspace-stock\stock-api
python -m pip install -r requirements.txt
```

---

## 4. 启动方法

### 方式一：直接启动批处理

```powershell
cd <OPENCLAW_HOME>\workspace-stock\stock-api
.\start.bat
```

这个脚本会做几件事：

- 清理 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`
- 设置 `NO_PROXY=*`
- 使用 `uvicorn` 在 `127.0.0.1:7070` 启动服务
- 固定 `--workers 1`
- 服务退出后自动拉起

### 方式二：直接运行 uvicorn

```powershell
cd <OPENCLAW_HOME>\workspace-stock\stock-api
$env:HTTP_PROXY=''
$env:HTTPS_PROXY=''
$env:ALL_PROXY=''
$env:NO_PROXY='*'
python -m uvicorn main:app --host 127.0.0.1 --port 7070 --workers 1
```

不建议改成多 worker，因为当前缓存是进程内字典。

---

## 5. 使用方法

### 5.1 命令行直接调接口

健康检查：

```powershell
C:\Windows\System32\curl.exe --silent --show-error --max-time 8 "http://127.0.0.1:7070/health"
```

A 股行情：

```powershell
C:\Windows\System32\curl.exe --silent --show-error --max-time 8 "http://127.0.0.1:7070/quote?symbol=600519"
```

港股行情：

```powershell
C:\Windows\System32\curl.exe --silent --show-error --max-time 8 "http://127.0.0.1:7070/quote?symbol=00700.HK"
```

A 股资金流：

```powershell
C:\Windows\System32\curl.exe --silent --show-error --max-time 8 "http://127.0.0.1:7070/flow?symbol=600941"
```

A 股公告：

```powershell
C:\Windows\System32\curl.exe --silent --show-error --max-time 8 "http://127.0.0.1:7070/get?symbol=601398"
```

全市场总览：

```powershell
C:\Windows\System32\curl.exe --silent --show-error --max-time 30 "http://127.0.0.1:7070/market/summary"
```

### 5.2 通过 Telegram 机器人使用

常见命令映射：

- `/quote 600519`
  - 对应 `GET /quote?symbol=600519`

- `/flow 600941`
  - 对应 `GET /flow?symbol=600941`

- `/get 601398`
  - 对应 `GET /get?symbol=601398`

自然语言示例：

- `用本地 stock-api 看一下贵州茅台的实时价格`
- `查一下中国移动A股今天的资金流向`
- `用本地 stock-api 的 /market/summary 看一下今天A股收盘总览`

---

## 6. 测试方法

### 6.1 跑自动化测试

```powershell
cd <OPENCLAW_HOME>\workspace-stock\stock-api
pytest tests -v
```

### 6.2 最小人工检查

至少检查这几项：

1. `/health`
2. `/quote?symbol=600519`
3. `/get?symbol=601398`
4. `/market/summary`

---

## 7. 数据源说明

个股接口主要通过现有封装获取数据。

`/market/summary` 做过单独适配，因为全市场抓取更容易遇到上游限流、超时或封禁。

当前设计是：

- 优先抓实时全市场分页数据与关键指数
- 如果上游暂时不可用，回退到 `market_summary_snapshot.json`

这时返回里可能会出现：

- `stale`
- `stale_reason`

表示这次是快照兜底，不是刚刚实时抓取到的全量源。

---

## 8. 迁移方法

### 8.1 重装系统后恢复

建议备份这些内容：

- 整个目录：
  - `<OPENCLAW_HOME>\workspace-stock\stock-api`

- OpenClaw 工作区规则文件：
  - `<WORKSPACE_ROOT>\TOOLS.md`
  - `<WORKSPACE_ROOT>\AGENTS.md`

- OpenClaw 主配置：
  - `<OPENCLAW_HOME>\openclaw.json`

重装后恢复步骤：

1. 安装 Python
2. 恢复 `stock-api` 目录
3. 执行依赖安装
4. 恢复 `TOOLS.md`、`AGENTS.md`、`openclaw.json`
5. 启动 `stock-api`
6. 先测 `/health`
7. 再测 `/quote`、`/get`、`/market/summary`
8. 最后再去 Telegram 里验证机器人是否命中本地接口

### 8.2 迁移到另一台电脑

迁移时建议整体复制以下目录：

```text
<OPENCLAW_HOME>\workspace-stock\stock-api
```

然后在新电脑上：

1. 安装 Python
2. 安装依赖
3. 确保 `start.bat` 中的路径仍然正确
4. 确保新电脑上的 OpenClaw 工作区路径一致，或者同步调整相关配置
5. 恢复这些文件：
   - `TOOLS.md`
   - `AGENTS.md`
   - `openclaw.json`
6. 启动服务并测试

如果新电脑上的用户名或目录不同，需要重点检查：

- `start.bat` 里的绝对路径
- OpenClaw 里引用工作区的路径
- 计划任务里的启动目录和命令

---

## 9. 机器人接入要点

机器人侧要确保这些规则存在：

- 本地 stock-api 走 `http://127.0.0.1:7070`
- 不要对本地地址使用 `web_fetch`
- 用 `exec + C:\Windows\System32\curl.exe`
- 个股接口一般 `--max-time 8`
- `/market/summary` 使用更长超时
- 没有当前回合成功的本地调用，不要声称“已验证”

相关工作区文件：

- `<WORKSPACE_ROOT>\TOOLS.md`
- `<WORKSPACE_ROOT>\AGENTS.md`

---

## 10. 常见问题

### 10.1 `/health` 正常，但 `/market/summary` 超时

说明服务没挂，但全市场源可能慢、被限流或被封。

先看两点：

- 是否已经有快照兜底
- 机器人是否给了足够长的超时

### 10.2 机器人说“未验证”，但接口明明存在

常见原因：

- 当前回合没有真正调用本地接口
- 调用时超时了
- 还在沿用旧 session 里的失败结论

### 10.3 `/get 601398` 返回成了行情而不是公告

这不是接口本身问题，而是机器人命令解释层走错了。

正确映射应该是：

- `/get 601398` -> `GET /get?symbol=601398`
- `/quote 601398` -> `GET /quote?symbol=601398`

### 10.4 为什么不能开多 worker

因为缓存是进程内的。开多 worker 会导致：

- 缓存不共享
- 返回不一致
- 调试更麻烦

---

## 11. 后续可扩展方向

如果继续做，建议优先补这些：

- `/market/sectors`
  - 行业强弱排行
  - 概念强弱排行

- `/market/indices`
  - 更多指数单独输出

- `/market/limitup`
  - 涨停跌停家数
  - 连板统计
  - 炸板率

- 更完整的运行日志和审计日志

---

## 12. 当前结论

当前这个 `stock-api` 已经可以作为本地机器人行情服务稳定使用，尤其是：

- 个股查询链路已打通
- 公告接口已打通
- A 股全市场总览已打通
- 自动化测试通过
- 机器人已出现真实成功调用记录

后续如果重装系统或迁移到新电脑，只要把目录和 OpenClaw 配置一起恢复，整体可以较低成本复原。
