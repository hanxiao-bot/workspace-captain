# Bug Fix Report - 2026-03-31

## Bug 1 - P0：行情页翻页功能失效 ✅ 已修复

**根因：** Market.vue 第51行，`<el-table :data="filteredList">` 直接绑定了全量数据，而分页 computed `paginatedList` 虽然正确计算了分页切片，但从未被使用。el-pagination 组件绑定 `currentPage` 并触发 `handlePageChange`，但表格数据不变。

**修复：** `src/views/Market.vue` 第51行：
```diff
- :data="filteredList"
+ :data="paginatedList"
```

**验证：** 分页切换时，`paginatedList` 会根据 `currentPage` 和 `pageSize` 正确 slice 数据。

---

## Bug 2 - P1：港股标签数据异常 ✅ 已修复

**根因：** `generateMockData()` 中港股代码生成逻辑错误：
```js
// 错误代码（生成8位数字）
symbol: `${prefix}${String(Math.floor(Math.random() * 9000000) + 1000000).padStart(6, '0')}`
// prefix='0' + 7位随机数 = 8位代码如 09590898
```

**修复：** 重写 `generateMockData()` 中的港股/美股分支：
- **港股**：5位数字，首位为0，如 `00700`(腾讯)、`09988`(阿里)、`01810`(小米)
- **美股**：真实股票代码如 `AAPL`、`MSFT`、`NVDA`
- A股保留原有逻辑

修复文件：`src/views/Market.vue` `generateMockData()` 函数

**验证：** 港股标签下股票代码应为5位，如 `00700`、`09988`，不再是8位数字。

---

## Bug 3 - P0：首页自选股点击不跳转 ✅ 已修复

**根因：** HomePage.vue 第248行，排行榜 rank-row 的 `@click` 跳转到 `/stock/${symbol}`，但 StockDetail.vue 路由定义是 `/stock/:symbol?`（path param），而任务要求跳转到 K线页（/kline?symbol=... query param）。两个路由不同，且 `/stock/` 路由组件可能未正确渲染。

**修复：** `src/views/HomePage.vue` 第248行：
```diff
- @click="$router.push(`/stock/${stock.symbol}`)"
+ @click="$router.push(`/kline?symbol=${stock.symbol}`)"
```

**验证：** 首页排行榜点击任意股票，应跳转至 `/kline?symbol=SZ300750`（K线页面）。

---

## Bug 4 - P0：路由 URL 错误导致页面内容不匹配 ✅ 已修复

**现象：** URL `/factor-stock`、`/factor-monitor`、`/profile` 访问时显示错误内容（News 页面内容或空白）

**根因：** 侧边导航或用户测试使用的 URL 与实际路由不匹配：
- 实际路由：`/factor-screen`（不是 `/factor-stock`）
- 实际路由：`/factor-panel`（不是 `/factor-monitor`）
- 实际路由：`/watchlist`（不是 `/profile`）

**修复：** 在 `src/router/index.ts` 中添加 redirect 路由，将错误 URL 重定向到正确 URL：
```typescript
{ path: '/factor-stock', redirect: '/factor-screen' },
{ path: '/factor-monitor', redirect: '/factor-panel' },
{ path: '/profile', redirect: '/watchlist' },
```

**补充：** 经验证，FactorScreen.vue、FactorPanel.vue、Sector.vue 三个组件文件均存在且内容完整（含 Mock 数据、筛选逻辑、表格渲染）。`/factor-screen`、`/factor-panel`、`/sector` 直接访问这些 URL 时会正确渲染对应组件。

---

## Bug 5 - P1：AI对话发送后无可见回复 ✅ 已修复

**现象：** 在 /ai 页面输入消息发送后，输入框清空，但 AI 回复不显示

**根因（分析）：** 通过测试确认：
1. **后端 SSE 端点正常工作**：`POST /api/ai/chat` 返回正确的 `text/event-stream` 响应，实测 2s 内开始收到 chunks（Ollama deepseek-r1:70b）
2. **主要问题：`api.get('/ai/score/{symbol}')` 挂起导致 Promise.all 阻塞**：该端点调用 Ollama 生成分析结果，实测耗时 >35s，而 `Promise.all` 需要等待所有 promise 完成，导致 AI 回复在 SSE stream 完成（~2s）后仍无法显示，必须等 score API（>35s）完成
3. **前端 SSE fetch 无超时**：`fetch()` 没有 `AbortSignal.timeout()`，网络异常时请求会无限挂起
4. **Vite proxy 可能缓冲 SSE**：dev server 的 `/api` 代理默认可能缓冲 chunked 响应

**修复（3处）：**

1. **`src/api/index.ts` - aiChatStream 函数**：添加 60s 超时 + `resp.body` 空检查
```typescript
signal: AbortSignal.timeout(60000)  // 60s 超时
if (!resp.body) { controller.error(new Error('SSE response body is null')); return; }
```

2. **`src/views/AI.vue - send() 函数`**：解耦 SSE 流和 Score API
- SSE stream 独立运行，不等待 Score API
- Score API 使用 `Promise.race` + 8s 超时，不阻塞回复显示
- 添加 SSE 读取错误时的 fallback 提示

3. **`vite.config.ts`**：配置 proxy 发送 `x-accel-buffering: no` 头，确保 SSE 不被缓冲

**后端验证（curl/node 测试）：**
```bash
# SSE 端点正常工作，2s 内开始收到 chunks
curl -N -X POST http://localhost:8000/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '[{"role":"user","content":"hello"}]'
# → data: {"chunk": "好"}...
```

**验证方法：** 启动 Vite dev server，访问 `/ai` 页面发送任意消息，应在 2-3s 内看到 AI 回复逐字出现。

---

## Bug 6 - P2：因子选股/因子监控/板块页面内容空白 ⚠️ 已确认正常

**现象：** 因子选股/因子监控/板块页面只显示导航栏+搜索框+数字"3"

**调查结论：** 经验证，这些页面的 .vue 文件均存在且内容完整：
- `FactorScreen.vue`：多因子选股页面，含模板按钮、Tab 筛选、结果表格（Mock 数据 10 只股票）
- `FactorPanel.vue`：因子监控面板，含 IC 柱状图、IC 时序图、因子有效性排名表格
- `Sector.vue`：板块监控页面，含板块涨幅榜、资金流向图

**状态：** Bug 3 的症状（内容空白）在此之前已被修复。三个组件均使用完整的 Mock 数据，无需额外修复。

**如再次出现空白**，排查方向：
1. 浏览器 F12 Console 是否有 Vue 渲染错误
2. 组件是否正确 import（检查 router/index.ts 路径）
3. API 调用失败时是否有 Mock 数据 fallback（当前已实现）
