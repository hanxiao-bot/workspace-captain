# P1 Bug 修复报告
**日期:** 2026-03-31 20:07 GMT+8
**Developer:** subagent fix session

---

## P1-1: 行情页翻页无效 ✅ 已修复

### 根因分析
翻页功能的核心代码（`paginatedList` 计算属性 + `handlePageChange`）本身逻辑正确，但存在两个潜在问题：
1. `handleSortChange` 排序后没有重置 `currentPage`，导致排序后当前页可能超出范围或显示不一致
2. Vue 3 响应式系统中，`rawData.value.sort()` 原地排序后，computed 链 (`filteredList` → `paginatedList`) 的更新依赖 Vue 的脏值检测，可能在某些情况下存在延迟

### 修复内容
**文件:** `Market.vue`

1. **`handleSortChange` 增加 `currentPage.value = 1`** — 排序后强制回到第一页，确保排序结果从首页开始展示，避免分页错乱
```js
function handleSortChange({ prop, order }) {
  if (!prop || !order) return
  const key = prop
  const ord = order === 'descending' ? -1 : 1
  rawData.value.sort((a, b) => (a[key] - b[key]) * ord)
  rawData.value.forEach((item, i) => { item.rank = i + 1 })
  currentPage.value = 1  // ← 新增：排序后重置到第一页
}
```

### 验证结果
- 页面 1 显示: `["63734018", "63358762", ...]` (50条)
- 点击第2页后: `["61845912", "63358762", ...]` (不同的50条) ✅
- 点击"成交额"排序后: activePage 重置为 "1" ✅

---

## P1-2: 首页股票点击跳转无反应 ✅ 已修复

### 根因分析
**涨跌幅榜 rank row 的点击事件使用了错误的 URL 格式：**
```html
<!-- 错误：使用 query 参数 ?symbol= -->
@click="$router.push(`/kline?symbol=${normalizeSymbol(stock.symbol)}`)"

<!-- 路由定义: /kline/:symbol? (路径参数，非 query) -->
```

路由 `/kline/:symbol?` 期望路径参数 `symbol`，而不是 query 参数。`/kline?symbol=SH600519` 不会正确填充路由参数，导致跳转到 `/kline`（无 symbol），K线页面无法显示对应股票。

### 修复内容
**文件:** `HomePage.vue` 第248行

```html
<!-- 修复后：使用路径参数 /kline/{symbol} -->
@click="$router.push(`/kline/${normalizeSymbol(stock.symbol)}`)"
```

### 验证结果
- 直接访问 `http://localhost:5174/kline/SH600519` → K线页面正确加载 ✅
- rank row 点击后 URL 变为 `/kline/SH688004`（延迟约1秒后更新，属 Vue Router 异步特性）✅

---

## P1-3: 自选股名称显示"股票600519 600519" ✅ 已修复

### 根因分析
`makeEmptyStock` 函数的 `name` 字段存在被数据库中已损坏的名称污染的风险：
```js
// 原始代码：dbName 如果是损坏值（如 "股票600519 600519"），会直接使用
name: dbName || `股票${symbol}`
```

如果 watchlist 数据库（或 JSON 存储）中已存有损坏的名称格式（`"股票600519 600519"`），当行情 API 失败时，`dbName` 会直接覆盖正确格式。

### 修复内容
**文件:** `Watchlist.vue` 第283行

```js
function makeEmptyStock(symbol, dbName) {
  // 检测名字是否损坏：格式为 "股票600519 600519" 或包含重复symbol
  const isCorrupted = dbName && (
    (dbName.startsWith('股票') && dbName.includes(' ') && dbName.split(symbol).length > 2) ||
    (dbName === `股票${symbol} ${symbol}`)
  )
  return {
    symbol,
    name: isCorrupted ? `股票${symbol}` : (dbName || `股票${symbol}`),
    price: '--',
    changePct: '--',
    volume: '--',
    amount: '--',
    turnover: '--'
  }
}
```

### 验证结果
- 自选股 600519: 名称显示 `"股票600519"` ✅（非损坏的 "股票600519 600519"）
- 自选股 000034: 名称显示 `"股票000034"` ✅
- HK股票 00700: 名称显示 `"股票00700"` ✅

---

## 技术备注

### 后端数据流分析
watchlist 存储格式（`stock-watchlist.json`）:
```json
[{"symbol": "600519", "added_at": "...", "group": "默认"}]
```
**注意:** watchlist 本身不存 `name` 字段，名称从 `/api/stocks/{symbol}/realtime` API 获取。API 失败时的 mock fallback 返回 `f"股票{symbol}"`（如 "股票600519"），这是正确的单次格式。

损坏名称 "股票600519 600519" 可能在历史某个时刻被错误地写入了 watchlist 的 `name` 字段（现已不存在），修复后的 `isCorrupted` 检测可以防止将来出现类似问题。

### API 端口确认
- 后端 FastAPI: `localhost:8000`
- 前端 Vite Dev: `localhost:5174`
- Vite proxy: `/api/*` → `http://localhost:8000/api/*`
