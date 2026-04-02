# MEMORY.md - Captain 长期记忆

---

## 关于我
- **Name:** Captain
- **Role:** AI 总指挥 / 任务调度总监 🧑‍✈️

---

## ⚠️ 铁律（2026-04-01 教训·永久）

### 绝对禁止

| 禁令 | 说明 |
|------|------|
| 🚫 不自己动手改代码 | 所有代码修改必须通过 sub-agent |
| 🚫 不直接 exec 修改文件 | workspace 目录外文件绝对不动 |
| 🚫 不绕过 sub-agent | 调度者职责是调度，不是执行 |

### 正确流程

```
发现需求 → 分析 → 派 sub-agent → 验证 → 汇报
```

### 错误示范

```
2026-04-01：直接 exec sed 修改 market.py
→ sed -i ':$' 破坏语法
→ 触发安全机制
→ exec 被封，文件损坏
教训：必须走 sub-agent
```

---

## 关于 Shawn（最高决策者）
- **ID:** ou_bbae622ad5e899d0ad6d4bc9055eeafb
- **时区:** Asia/Shanghai（GMT+8）
- **平台:** 飞书（主要）+ Webchat
- **偏好:** 快速交付、有问题直接说、多用中文

---

## 当前服务状态（2026-04-01）

| 服务 | 端口 | 状态 |
|------|------|------|
| Memos | 5230 | ✅ 运行中 |
| 股票系统后端 | 8000 | ✅ 运行中（部分API有mock数据）|
| 股票系统前端 | 5174 | ✅ 运行中 |
| Ollama | 11434 | 未确认 |

---

## 已完成项目

### 项目一：日志清理脚本
- **时间:** 2026-03-28 00:38
- **文件:** `/Users/dc/.openclaw/workspace-captain/logs/cleaner.py`
- **状态:** ✅ 已完成

### 项目二：股票分析系统
- **时间:** 2026-03-19 至今
- **前端:** `/Users/dc/.openclaw/workspace/clawd-stock-vue/`（Vue3）
- **后端:** `/Users/dc/clawd/stock-analysis-system/`（FastAPI）
- **状态:** ✅ 主要功能已完成，部分功能验证进行中

#### 03-31 里程碑完成
| 功能 | 详情 |
|------|------|
| 数据库 cron 修复 | 切换 `quotes` → `daily_quotes` 表，数据恢复正常 |
| 因子模块真实逻辑 | 估值(PE/PB) + 成长(营收/净利增速/毛利率/净利率) + 量价(动量/主力净流入/换手率/波动率) |
| AI 对话 + Ollama | `POST /api/ai/chat` SSE流式，`deepseek-r1:70b` 本地模型 |
| 策略回测引擎 | MA/RSI/MACD/布林带/KDJ 5大策略，含夏普比率/最大回撤/胜率 |
| 移动端适配 | Market/KLine/Watchlist/AppLayout 4文件，768px/480px断点 |
| 前端双端口验证 | 5174 ✅ 5175 ✅ |
| 后端健康检查 | 8000 PID 97857，`/api/health` ✅ database connected |
| stocks 数据量 | 5328条，日期 2026-03-30 |

### 已完成功能
- 港股指数 / 行情字段 / K线指标(7个) / 自选股 / 财务数据 / 选股器(14模板)
- 资讯页面 / 预警页面 / 板块监控 / 组合对比 / 盘口+成交明细
- 飞书机器人「球球」+「爪爪」双账号
- AI综合研判 `/ai` 页面

### 待完成功能
- 行情分页 `/market` API修复（进行中）

---

## 重要教训

- 子Agent任务完成后必须验证，不能盲目信任
- exec 直接写代码比子Agent更可靠（但有边界风险）
- 本地模型(qwen3:32b) 思考输出太长，不适合代码生成
- **所有代码修改必须走 sub-agent，不能自己动手**

---

## Skills 状态

| Skill | 用途 |
|--------|------|
| clawsec | 安全审计 |
| deep-debugging | 结构化调试 |
| self-improving-agent | 错误学习 |
| github | GitHub CLI |
| tavily-search | 联网搜索 |
| multi-search-engine | 多搜索引擎 |
| last30days | 舆情研究（mock可用）|
| lightpanda | 轻量无头浏览器（已下载未集成）|

---

## 今日新增项目（2026-04-01）

### 新项目发现（观望中）
- DeerFlow（字节）：多Agent编排框架
- MiroFish（盛大）：群体智能舆情推演
- TradingAgents：多智能体金融交易框架

---

## 股票系统验证状态（2026-04-02 更新）

| 页面 | 问题 | 状态 |
|------|------|------|
| 行情分页 `/market` | API有响应但返回mock数据，非真实Sina数据 | ⚠️ 进行中 |
| K线 `/kline` | 数据已恢复正常（daily_quotes） | ✅ 已验证 |
| 因子面板 `/factor-panel` | 真实因子计算上线（PE/PB/成长/量价） | ✅ 已完成 |
| AI 对话 `/ai` | deepseek-r1:70b 流式输出 | ✅ 已完成 |
| 策略回测 `/backtest` | MA/RSI/MACD/布林带/KDJ 5大策略 | ✅ 已完成 |
| 移动端适配 | 4文件 768px/480px断点 | ✅ 已完成 |


