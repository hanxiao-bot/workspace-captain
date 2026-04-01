# Stock CLI Design Specification
# 基于 cli-anything 方法论，为股票分析系统设计的标准化 CLI

> 版本: v0.1.0 | 状态: 设计中 | 生成日期: 2026-03-28

---

## 一、系统现状分析

### 1.1 技术栈

| 组件 | 技术 | 端口/路径 |
|------|------|----------|
| 前端 | Vue3 + Vite | localhost:5174 |
| 后端 | FastAPI + Uvicorn | localhost:8000 |
| 数据库 | SQLite | /Users/dc/clawd/stock-analysis-system/data/stocks.db |
| 数据源 | akshare | Python 库 |
| 大模型 | Ollama | localhost:11434 |

### 1.2 现有 API 路由（已实现）

```
GET  /api/stocks                     # 股票列表
GET  /api/stocks/{symbol}           # 单股信息
GET  /api/stocks/{symbol}/realtime  # 实时行情
GET  /api/stocks/{symbol}/quotes    # 成交明细
GET  /api/kline/{symbol}            # K线数据
GET  /api/kline/{symbol}/fq        # 前复权/后复权
GET  /api/minute/{symbol}          # 分时数据
GET  /api/orderbook/{symbol}       # 盘口数据
GET  /api/deals/{symbol}           # 成交明细
GET  /api/financial/{symbol}       # 财务数据
GET  /api/market/index              # 大盘指数
GET  /api/market/limit              # 涨跌停
GET  /api/market/sector             # 板块数据
GET  /api/market/rank               # 排行榜
GET  /api/market/capital_flow       # 资金流向
GET  /api/market/northbound         # 北向资金
GET  /api/market/etf                # ETF数据
GET  /api/news                      # 综合资讯
GET  /api/news/cls                  # 财联社资讯
GET  /api/news/sina                 # 新浪资讯
GET  /api/ai/score/{symbol}         # AI评分
GET  /api/ai/stock_pool            # 选股池
GET  /api/watchlist                # 自选股
GET  /api/alerts                   # 预警列表
GET  /api/alerts/{alert_id}        # 单条预警
GET  /api/backtest                 # 策略回测
GET  /api/factors/list             # 因子列表
POST /api/factors/calculate        # 因子计算
GET  /api/factors/monitor          # 因子监控
POST /api/factors/generate_strategy # 因子策略生成
```

### 1.3 待完成功能

- 数据库每日 cron（数据停在 03-22）
- 因子模块真实逻辑
- AI 对话功能对接本地大模型
- 策略回测引擎
- 移动端适配

---

## 二、CLI 架构设计

### 2.1 设计原则

1. **子命令模式**：一级命令 = 功能域，二级命令 = 操作
2. **输出双模**：默认人类可读表格，支持 `--json` 输出 JSON
3. **状态模型**：无状态设计（所有状态在 FastAPI 后端）
4. **兼容 REPL**：支持交互模式和单次执行

### 2.2 命令分组

```
stock-cli.py
├── get         # 数据查询（行情/K线/财务）
├── screener    # 选股器
├── alert       # 预警管理
├── backtest    # 回测引擎
├── factor      # 因子管理
├── news        # 资讯查询
├── market      # 大盘/板块
├── watchlist   # 自选股管理
├── system      # 系统运维
└── help        # 帮助
```

### 2.3 输出格式规范

```bash
# 人类可读（默认）
$ stock-cli.py get kline 000001
股票代码  日期        开盘    最高    最低    收盘    成交量
000001   2026-03-28  12.50   12.80   12.30   12.75   1250000

# JSON 模式（--json）
$ stock-cli.py get kline 000001 --json
{
  "status": "success",
  "data": [
    {
      "symbol": "000001",
      "date": "2026-03-28",
      "open": 12.50,
      "high": 12.80,
      "low": 12.30,
      "close": 12.75,
      "volume": 1250000
    }
  ]
}
```

---

## 三、命令详细设计

### 3.1 `get` — 数据查询

```
get <subcommand> [options]
```

| 子命令 | 功能 | 示例 |
|--------|------|------|
| `kline` | K线数据 | `get kline 000001 --period 1d --indicators MA,MACD` |
| `realtime` | 实时行情 | `get realtime 000001,600519` |
| `minute` | 分时数据 | `get minute 000001` |
| `orderbook` | 盘口数据 | `get orderbook 000001` |
| `deals` | 成交明细 | `get deals 000001 --limit 50` |
| `financial` | 财务数据 | `get financial 000001` |
| `profile` | 股票概况 | `get profile 000001` |

**通用选项：**
```
--json           输出JSON格式
--period <p>    周期: 1m/5m/15m/30m/1h/1d/1w (默认: 1d)
--start <date>  开始日期 (YYYY-MM-DD)
--end <date>    结束日期 (YYYY-MM-DD)
--indicators    技术指标: MA,MACD,KDJ,RSI,BOLL (逗号分隔)
```

### 3.2 `screener` — 选股器

```
screener <subcommand> [options]
```

| 子命令 | 功能 | 示例 |
|--------|------|------|
| `list` | 列出所有模板 | `screener list` |
| `run` | 执行选股 | `screener run momentum --limit 20` |
| ` templates` | 查看模板列表 | `screener templates` |

**内置模板：**
- `momentum` — 动量策略
- `value` — 价值筛选（低PE/PB/高ROE）
- `growth` — 成长股筛选
- `high-turnover` — 高换手率
- `limit-up` — 涨停股
- `northbound-hold` — 北向持股

### 3.3 `alert` — 预警管理

```
alert <subcommand> [options]
```

| 子命令 | 功能 | 示例 |
|--------|------|------|
| `list` | 列出所有预警 | `alert list` |
| `create` | 创建预警 | `alert create --symbol 000001 --condition "pe > 20"` |
| `test` | 测试预警 | `alert test <alert_id>` |
| `delete` | 删除预警 | `alert delete <alert_id>` |

**condition 语法：**
```
pe > 20
pb < 3
change_pct > 5
volume > 10000000
roe >= 15
```

### 3.4 `backtest` — 回测引擎

```
backtest [options]
```

| 选项 | 说明 | 示例 |
|------|------|------|
| `--symbol` | 股票代码 | `--symbol 000001` |
| `--strategy` | 策略名称 | `--strategy rsi` |
| `--start` | 开始日期 | `--start 2026-01-01` |
| `--end` | 结束日期 | `--end 2026-03-28` |
| `--init-cash` | 初始资金 | `--init-cash 100000` |

**策略列表：**
- `rsi` — RSI 相对强弱指标
- `ma_cross` — 均线交叉
- `macd` — MACD 策略

**输出示例：**
```
策略回测报告: RSI
股票: 000001 平安银行
时间: 2026-01-01 ~ 2026-03-28

收益统计:
  总收益率: +12.5%
  年化收益率: +52.3%
  最大回撤: -8.2%
  夏普比率: 1.85

交易统计:
  总交易次数: 24
  胜率: 62.5%
  平均持仓天数: 5.2
```

### 3.5 `factor` — 因子管理

```
factor <subcommand> [options]
```

| 子命令 | 功能 | 示例 |
|--------|------|------|
| `list` | 因子列表 | `factor list` |
| `calculate` | 计算因子 | `factor calculate --factors pe,pb,roe` |
| `monitor` | 因子监控 | `factor monitor --factor pe` |
| `generate` | 生成策略 | `factor generate --factors pe,roe --weights 0.6,0.4` |

### 3.6 `news` — 资讯查询

```
news [options]
```

| 选项 | 说明 | 示例 |
|------|------|------|
| `--source` | 来源: cls/sina/all | `--source cls` |
| `--category` | 分类 | `--category宏观` |
| `--limit` | 条数 | `--limit 20` |

**示例：**
```
$ stock-cli.py news --source cls --limit 10
时间        来源  标题
──────────  ────  ──────────────────────────
10:30      财联社  央行开展MLF操作，利率持平
09:45      财联社  比亚迪发布新车型
...
```

### 3.7 `market` — 大盘/板块

```
market <subcommand> [options]
```

| 子命令 | 功能 | 示例 |
|--------|------|------|
| `index` | 大盘指数 | `market index` |
| `sector` | 板块数据 | `market sector --type industry` |
| `rank` | 排行榜 | `market rank --type rise --limit 20` |
| `capital-flow` | 资金流向 | `market capital-flow` |
| `northbound` | 北向资金 | `market northbound` |

### 3.8 `watchlist` — 自选股管理

```
watchlist <subcommand> [options]
```

| 子命令 | 功能 | 示例 |
|--------|------|------|
| `list` | 查看自选股 | `watchlist list` |
| `add` | 添加自选 | `watchlist add 000001` |
| `remove` | 移除自选 | `watchlist remove 000001` |
| `quotes` | 自选股实时行情 | `watchlist quotes` |

### 3.9 `system` — 系统运维

```
system <subcommand> [options]
```

| 子命令 | 功能 | 示例 |
|--------|------|------|
| `health` | 服务健康检查 | `system health` |
| `status` | 实时状态 | `system status` |
| `restart` | 重启服务 | `system restart --service backend` |
| `logs` | 查看日志 | `system logs --service backend --lines 50` |
| `db` | 数据库状态 | `system db --check` |

**`system health` 输出示例：**
```
服务健康检查:

✅ Vue3 Frontend    localhost:5174  200 OK
✅ FastAPI Backend  localhost:8000  200 OK
✅ Ollama           localhost:11434 200 OK
✅ Memos            localhost:5230  200 OK
✅ 数据库           stocks.db       连接正常 (最后更新: 2026-03-22)

总体状态: ⚠️  数据库数据落后 6 天
```

---

## 四、文件结构设计

```
stock-analysis-system/
└── cli/
    ├── stock_cli.py              # 主入口 (Click CLI)
    ├── core/
    │   ├── api_client.py         # FastAPI HTTP 客户端
    │   ├── formatters.py         # 输出格式化 (table/json)
    │   ├── config.py             # 配置管理
    │   └── exceptions.py         # 自定义异常
    ├── commands/
    │   ├── get.py                # get 命令组
    │   ├── screener.py           # screener 命令组
    │   ├── alert.py              # alert 命令组
    │   ├── backtest.py           # backtest 命令组
    │   ├── factor.py             # factor 命令组
    │   ├── news.py               # news 命令组
    │   ├── market.py             # market 命令组
    │   ├── watchlist.py          # watchlist 命令组
    │   └── system.py             # system 命令组
    ├── tests/
    │   ├── TEST.md               # 测试计划
    │   ├── test_api_client.py    # API 客户端测试
    │   ├── test_commands.py      # 命令测试
    │   └── test_e2e.py          # E2E 测试
    ├── setup.py                  # PyPI 配置
    └── README.md                 # 安装使用说明
```

---

## 五、实施计划

### Phase 1: 核心骨架 (Day 1)
- [ ] 创建 CLI 目录结构
- [ ] 实现 `stock_cli.py` 主入口（Click框架）
- [ ] 实现 `api_client.py`（统一HTTP调用层）
- [ ] 实现基础 formatters（table + JSON）
- [ ] 绑定 `system health` 命令

### Phase 2: 核心命令 (Day 2)
- [ ] 实现 `get` 命令组（kline/realtime/minute/orderbook）
- [ ] 实现 `screener` 命令组
- [ ] 实现 `market` 命令组
- [ ] 实现 `watchlist` 命令组

### Phase 3: 高级命令 (Day 3)
- [ ] 实现 `alert` 命令组
- [ ] 实现 `backtest` 命令组
- [ ] 实现 `factor` 命令组
- [ ] 实现 `news` 命令组

### Phase 4: 测试与文档 (Day 4)
- [ ] 编写单元测试
- [ ] 编写 E2E 测试
- [ ] 完善 README
- [ ] 发布到 PyPI

---

## 六、关键技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| CLI 框架 | Click | 官方推荐，subcommand 支持好 |
| HTTP 客户端 | httpx | 同步/异步都支持 |
| 输出格式 | Rich + JSON | 表格彩色输出，JSON便于管道 |
| 状态存储 | 无状态 | 所有状态在后端，CLI只调用 |
| 安装方式 | PyPI + brew | 双渠道分发 |

---

## 七、成功标准

1. ✅ `stock-cli.py --help` 显示完整帮助
2. ✅ `stock-cli.py system health` 正确报告所有服务状态
3. ✅ `stock-cli.py get kline 000001 --json` 返回有效 JSON
4. ✅ `stock-cli.py screener run momentum --limit 10` 显示选股结果
5. ✅ 所有命令支持 `--json` 机器可读输出
6. ✅ 单元测试覆盖率 > 80%
7. ✅ E2E 测试全部通过
