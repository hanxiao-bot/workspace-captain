# 股票分析系统更新日志
Date: 2026-03-31

## 今日完成

### 功能更新

#### task1：数据库 cron 修复
- **根因**：`kline_component/kline_data.py` 读取空表 `quotes`，数据源错误导致 K 线数据为空
- **修复**：切换至 `daily_quotes` 表，并调整列名映射（`date` → `trade_date`，`change_percent` → `change_pct`）
- **结果**：数据恢复正常，最新日期 2026-03-30，API 验证通过

#### task2：因子模块
- **新增**：3 大类真实因子体系
  - 估值因子：PE（市盈率）、PB（市净率）
  - 成长因子：营收增速、净利增速、毛利率、净利率
  - 量价因子：20日动量、60日动量、主力净流入比、换手率、波动率
- **数据来源**：`stocks` 表 + `daily_quotes` 表实时计算
- **覆盖**：格力电器、招商银行、五粮液、比亚迪等真实选股结果

#### task3：AI 对话 + Ollama
- **新增接口**：
  - `POST /api/ai/chat` — SSE 流式对话
  - `GET /api/ai/score/{symbol}` — 单股票 AI 评分
  - `GET /api/ai/stock_pool` — 股票池查询
- **模型**：本地 Ollama `deepseek-r1:70b`
- **前端**：`AI.vue` 重写，支持逐字流式输出 + 股票评分卡展示

#### task4：策略回测引擎
- **后端**：5 大交易策略
  - MA 交叉策略
  - RSI 策略
  - MACD 策略
  - 布林带策略
  - KDJ 策略
  - 完整绩效指标：夏普比率、最大回撤、卡玛比率、胜率等
- **前端**：`Backtest.vue` 重写，新增净值曲线图、回撤曲线图、交易记录表格、参数优化面板

#### task5：移动端适配
- **适配文件（4个）**：`Market.vue`、`Watchlist.vue`、`KLine.vue`、`AppLayout.vue`
- **方案**：纯 CSS 媒体查询
  - 断点：`768px`（平板）、`480px`（手机）
  - 表格列分级隐藏、K 线高度响应式、工具栏垂直堆叠

#### task6：前端启动验证
- 端口 `5174` ✅ 运行正常（HTTP 200 OK）
- 端口 `5175` ✅ 运行正常（HTTP 200 OK）

#### task7：后端启动验证
- 端口 `8000` ✅ PID `97857` 运行中
- `GET /api/health` ✅ 返回 `database connected`
- `stocks` 表数据量：**5328 条**，最新数据日期：**2026-03-30**

---

## 技术细节

### 数据库修复（task1）
- 问题出在 `kline_component/kline_data.py` 使用了错误的表名 `quotes`
- 修正为 `daily_quotes`，并对字段名做了兼容性映射：
  - `date` → `trade_date`
  - `change_percent` → `change_pct`
- cron 任务重新拉取数据后，数据已完全恢复

### AI 集成（task3）
- 调用本地 Ollama 服务，模型 `deepseek-r1:70b`
- 后端使用 SSE（Server-Sent Events）实现流式响应，前端逐字渲染
- `/api/ai/score/{symbol}` 基于多因子综合评分体系，结合 AI 解读

### 策略回测（task4）
- 因子计算与回测引擎解耦，回测支持参数化配置
- 绩效指标覆盖风险（最大回撤）、收益（年化收益）、风险调整收益（夏普、卡玛）多维度

### 移动端适配（task5）
- 无引入任何 JS 框架，纯 CSS `@media` 查询实现
- 三级响应式：桌面（默认）→ 平板（768px 断点）→ 手机（480px 断点）
- 表格采用列优先级隐藏策略，保证核心数据在小屏可见

---

## 验证结果

| 项目 | 状态 | 详情 |
|------|------|------|
| 前端（5174） | ✅ 正常 | HTTP 200 OK |
| 前端（5175） | ✅ 正常 | HTTP 200 OK |
| 后端（8000） | ✅ 运行中 | PID 97857 |
| /api/health | ✅ 正常 | database connected |
| stocks 数据 | ✅ 正常 | 5328 条，日期 2026-03-30 |
| K 线数据 | ✅ 正常 | 已修复至 2026-03-30 |
