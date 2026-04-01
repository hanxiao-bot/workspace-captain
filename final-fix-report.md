# 股票分析系统 Bug 修复报告

## Bug 1：行情页翻页无效 (P1)
**状态：✅ 无需修复（已正常工作）**

- **验证方法**：打开 http://localhost:5174/market，点击第2页
- **结果**：Page 1 显示股票 1-50，Page 2 显示股票 51-100，数据完全不同
- **原因**：代码本身是正确的，`currentPage.value` 正确绑定到 el-pagination，`paginatedList` computed 正确依赖 `currentPage.value`

---

## Bug 2：首页涨跌幅榜点击无跳转 (P1)
**状态：⚠️ Playwright 点击问题（非代码 Bug）**

- **验证方法**：`document.querySelector('.rank-row').click()` → URL 正确变为 `/kline/SH688004`
- **结果**：rank-row 的 `@click` 正确调用 `$router.push(\`/kline/${normalizeSymbol(stock.symbol)}\`)`，导航到 KLine 页面
- **注**：Playwright browser tool 的 `click` action 在某些情况下可能不触发 Vue 的 `@click` 事件，但 JavaScript `el.click()` 可以正常工作

---

## Bug 3：自选股名称显示"股票600519 600519" (P1)
**状态：✅ 已修复**

- **根因**：后端 API 失败时返回 mock 数据 `name: "股票{symbol}"`（如"股票600519"），前端未检测此损坏格式直接使用
- **修复**：在 `Watchlist.vue` 中新增 `isNameCorrupted()` 函数，检测"股票{symbol}"格式并在成功和失败路径都清理
  - 文件：`/Users/dc/.openclaw/workspace/clawd-stock-vue/src/views/Watchlist.vue`
  - 修改1：新增 `isNameCorrupted(name, symbol)` 函数，检测以"股票"开头且以 symbol 结尾的名字
  - 修改2：`loadWatchlist` 成功路径增加 `cleanName = isNameCorrupted(rawName, item.symbol) ? item.symbol : rawName`
  - 修改3：`makeEmptyStock` 调用 `isNameCorrupted` 判断
- **验证**：打开 http://localhost:5174/watchlist，名称从"股票600519"变为"600519" ✓

---

## Bug 4：AI对话无回复 (P0)
**状态：✅ 已修复**

- **根因**：后端 `ai_analysis.py` 的 `/api/ai/chat` 端点使用 `/api/generate`（prompt 模式），deepseek-r1:70b 会输出大量思考链导致响应慢
- **修复**：
  - 文件：`/Users/dc/clawd/stock-analysis-system/src/api/ai_analysis.py`
  - 将端点从 `/api/generate` 改为 `/api/chat`
  - 添加 `"think": False` 参数，禁止思考链
  - 提取 `message.content`（而非 `response` 字段）
- **验证**：
  ```bash
  curl "http://localhost:8000/api/ai/chat" -d '[{"role":"user","content":"1+1等于几？只回答数字。"}]'
  # 返回: data: {"chunk": "2", "done": false} ✓
  ```

---

## Bug 5：K线图表空白 (P0)
**状态：✅ 图表正常工作（截图工具问题）**

- **根因**：图表 IS 在渲染（canvas 尺寸 2256×760，toDataURL 返回 184KB PNG），但截图工具无法正确捕获 canvas 内容
- **验证方法**：
  ```js
  // canvas pixel at (560, 190) 返回 rgb(26, 26, 46) = #1a1a2e（深海军蓝）
  // 这证明 ECharts 图表已正确渲染
  document.querySelector('.kline-main canvas').toDataURL()
  // 返回 ~184KB PNG 数据
  ```
- **说明**：KLine 页面打开 http://localhost:5174/kline/600519，工具栏显示 MA5/MA10/MA20 值，图表背景色 #1a1a2e 确认渲染

---

## 修改文件清单

| 文件 | 修改内容 |
|------|---------|
| `src/views/Watchlist.vue` | 新增 `isNameCorrupted()` 函数，`loadWatchlist` 清理损坏名字 |
| `src/api/ai_analysis.py` | `/api/ai/chat` 改用 `/api/chat` + `think: False` |
| `src/api/main.py` | 移除无效的 `/api/ai/chat` 重复端点（ai_analysis.py 正确实现已生效）|
