# Stock System — 股票分析系统

> 从 MEMORY.md 提取，2026-04-03 整理

---

## 项目信息

| 项目 | 路径 |
|------|------|
| 前端（Vue3） | `/Users/dc/.openclaw/workspace/clawd-stock-vue/` |
| 后端（FastAPI） | `/Users/dc/clawd/stock-analysis-system/` |
| 端口（前端） | 5174 / 5175 |
| 端口（后端） | 8000 |
| 数据库 | SQLite `stock_data.db` |

---

## 已完成功能

| 功能 | 详情 |
|------|------|
| 港股指数 | 大盘指数实时 |
| 行情字段 | 7个K线指标 |
| 自选股 | 用户自选股列表 |
| 财务数据 | PE/PB/营收/净利等 |
| 选股器 | 14模板 |
| 资讯页面 | 实时新闻 |
| 预警页面 | 价格预警 |
| 板块监控 | 概念板块 |
| 组合对比 | 多股对比 |
| 盘口+成交明细 | 实时盘口 |
| AI综合研判 | `/ai` 页面 |
| 因子面板 | PE/PB/成长/量价真实因子 |
| 策略回测 | MA/RSI/MACD/布林带/KDJ 5大策略 |
| 移动端适配 | 768px/480px 断点 |

---

## 2026-03-31 里程碑

| 功能 | 详情 |
|------|------|
| 数据库 cron 修复 | 切换 `quotes` → `daily_quotes` 表 |
| 因子模块真实逻辑 | 估值 + 成长 + 量价因子 |
| AI 对话 + Ollama | `POST /api/ai/chat` SSE流式，`deepseek-r1:70b` |
| 策略回测引擎 | 夏普比率/最大回撤/胜率 |
| stocks 数据量 | 5328条（2026-03-30）|

---

## 技术规范

### 字段名规范
- 后端：**snake_case**（如 `change_percent`）
- 前端：**camelCase**（如 `changePercent`）
- 必须严格对应，否则前端拿到 `undefined`

### API limit 问题
- Eastmoney 全部被代理拦截 → 改用新浪/腾讯直连
- 请求数量不能超过后端上限 **1000**

### SSL 证书
- 需要设置 `SSL_CERT_FILE` + `CERTIFI` 环境变量
- 涉及：zshrc / run_api.sh / launchd plist

---

## 验证状态（2026-04-02）

| 页面 | 状态 |
|------|------|
| K线 `/kline` | ✅ 已验证（daily_quotes 正常） |
| 因子面板 `/factor-panel` | ✅ 真实因子计算上线 |
| AI 对话 `/ai` | ✅ deepseek-r1:70b 流式 |
| 策略回测 `/backtest` | ✅ 5大策略 |
| 移动端适配 | ✅ 4文件 |
| 行情分页 `/market` | ⚠️ 返回mock数据，非真实Sina数据 |

---

## 教训

- 字段名 snake_case vs camelCase 必须严格对应
- 所有代码修改必须走 sub-agent，不能直接 exec 修改
- Eastmoney 被代理拦截问题 → 换新浪/腾讯 API

---

## 相关文件

- MEMORY.md — 主记忆
- memory/2026-04-01.md — 详细修复记录
