# OpenClaw Session 压缩机制设计文档

> 版本: v1.0
> 日期: 2026-04-02
> 状态: 设计中

---

## 1. 背景与目标

OpenClaw 的 `claw-code`（pi-coding-agent）已有成熟的 Session 压缩机制，本设计将其中的核心逻辑提炼并适配到 OpenClaw 主框架层，作为跨 Agent 的通用能力。

**设计目标：**

- 会话历史超过 token 上限时，自动触发压缩
- 用 LLM 生成摘要替换历史消息，保留关键上下文
- 摘要可链式合并，支持多次压缩而不丢失重要信息
- 配置灵活可调，不过度压缩也不遗漏关键上下文

---

## 2. 现有机制分析

### 2.1 Session 数据结构

Session 以 JSONL 文件存储，每行一个 `SessionEntry`，支持树形结构（`id`/`parentId`）。

**核心消息类型：**

```typescript
type AgentMessage =
  | UserMessage          // 用户消息
  | AssistantMessage     // AI 回复
  | ToolResultMessage    // 工具执行结果
  | BashExecutionMessage // Bash 命令执行（pi-coding-agent 扩展）
  | CustomMessage        // 扩展自定义消息
  | BranchSummaryMessage  // 分支摘要
  | CompactionSummaryMessage; // 压缩摘要

interface SessionEntryBase {
  type: string;
  id: string;           // 8位十六进制ID
  parentId: string | null;
  timestamp: string;   // ISO 格式
}
```

**文件格式示例：**

```
{"type":"session","version":3,"id":"uuid","timestamp":"...","cwd":"/path/to/project"}
{"type":"message","id":"a1b2c3d4","parentId":null,...}
{"type":"message","id":"b2c3d4e5","parentId":"a1b2c3d4",...}
...
```

### 2.2 Token 计算方式

OpenClaw 采用两层 token 估算策略：

**策略 A — 使用 API 返回的真实 usage（优先）：**

```typescript
function calculateContextTokens(usage: Usage): number {
  // 优先使用 API 返回的 totalTokens
  if (usage.totalTokens) return usage.totalTokens;
  // fallback: 手动累加各分量
  return usage.input + usage.output + usage.cacheRead + usage.cacheWrite;
}
```

**策略 B — 字符估算（无 usage 时降级）：**

```typescript
function estimateTokens(message: AgentMessage): number {
  // 保守估算：字符数 / 4
  const text = extractMessageText(message);
  return Math.ceil(text.length / 4);
}
```

**会话级 token 估算：**

```typescript
function estimateContextTokens(messages: AgentMessage[]): ContextUsageEstimate {
  // 从最后一条有 usage 的 assistant message 获取真实 token 数
  // 加上后续消息的估算值
}
```

### 2.3 现有压缩流程（pi-coding-agent）

```
shouldCompact() → prepareCompaction() → compact() → 保存摘要 → 重载 Session
```

**`shouldCompact()` 触发判断：**

```typescript
function shouldCompact(
  contextTokens: number,      // 当前估算 token 数
  contextWindow: number,      // 模型上下文窗口上限
  settings: CompactionSettings // 压缩配置
): boolean {
  const threshold = contextWindow * settings.maxHistoryShare; // e.g., 0.7
  return contextTokens >= threshold;
}
```

---

## 3. 设计方案

### 3.1 配置参数

在 `agents.defaults.compaction` 下暴露以下配置：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | `boolean` | `true` | 是否启用压缩 |
| `reserveTokens` | `number` | `10000` | 为回复生成保留的 token 空间 |
| `keepRecentTokens` | `number` | `4000` | 保留最近 N token 不压缩 |
| `reserveTokensFloor` | `number` | `5000` | `reserveTokens` 的最小保证值 |
| `maxHistoryShare` | `number` | `0.7` | 压缩后历史最多占上下文的比例（0.1-0.9） |
| `recentTurnsPreserve` | `number` | `3` | 最近 N 个完整对话轮次原文保留 |
| `timeoutSeconds` | `number` | `900` | 单次压缩操作超时 |
| `truncateAfterCompaction` | `boolean` | `false` | 压缩后是否重写文件（去除已摘要条目） |
| `postIndexSync` | `"off" \| "async" \| "await"` | `"async"` | 压缩后是否触发 memory reindex |
| `model` | `string` | `null` | 压缩用的模型覆盖（默认使用 session 主模型） |

### 3.2 触发条件

**触发公式：**

```
当 (contextTokens + reserveTokens) >= (contextWindow * maxHistoryShare) 时触发压缩
```

即：当前上下文接近上限时，提前压缩，预留生成空间。

**判断时机：**
- 每次发送消息前检查（pre-flight check）
- 使用 `estimateContextTokens()` 估算当前会话总 token

### 3.3 保留策略（Cut Point 算法）

**目标：** 保留最近约 `keepRecentTokens` 的内容，其余压缩。

**算法（`findCutPoint`）：**

```
FUNC findCutPoint(entries, startIndex, endIndex, keepRecentTokens):
    accumulated = 0
    FOR i FROM endIndex - 1 DOWN TO startIndex:
        entry = entries[i]
        IF entry.type == "toolResult":  // 工具结果不独立计入
            CONTINUE
        tokens = estimateTokens(entry)
        accumulated += tokens
        IF accumulated >= keepRecentTokens:
            // 找到 cut point，回退到当前轮开始
            turnStart = findTurnStartIndex(entries, i, startIndex)
            RETURN { firstKeptEntryIndex: turnStart, isSplitTurn: (turnStart < i) }
    RETURN { firstKeptEntryIndex: startIndex, isSplitTurn: false }
```

**Turn 边界定义：** 一个 turn = 1 个 user/bashExecution + 1 个 assistant（及其 toolResults）

**规则：**
- cut point 永远在 user/bashExecution 消息边界，不切割 assistant 消息
- 保留最近 `recentTurnsPreserve` 个完整 turn 原文不压缩
- cut point 落在 turn 中间时，保留该 turn 的 user 部分

### 3.4 摘要生成算法

**输入：** 待压缩的消息块（按时间顺序）

**Prompt 模板：**

```
你是一个会话摘要生成器。请将以下对话历史压缩为简洁的摘要。

要求：
1. 保留关键决策、结论、用户偏好、重要上下文
2. 移除冗余对话、调试信息、重复尝试
3. 保留文件名、函数名、关键变量名、路径等标识符（不要改写）
4. 如果有之前的摘要，请在其基础上增量更新（UPDATE 模式）
5. 摘要语言与原对话一致

格式：
[COMPRESSED]
<1-2段话总结核心内容>
[/COMPRESSED]

{如果有 previousSummary}
[PREVIOUS SUMMARY]
{previousSummary}
[/PREVIOUS SUMMARY]

请生成摘要：
---
{messages to summarize}
---
```

**previousSummary 链式合并：**
- 每次压缩后，生成的摘要会存入 `CompactionSummaryMessage`
- 下次压缩时，将 `previousSummary` 作为输入的一部分传入，实现增量更新
- 最终摘要可追溯整个会话的关键脉络

### 3.5 链式合并策略

```
会话历史:  [Turn1] [Turn2] [Turn3] [Turn4] [Turn5] [Turn6] [Turn7] [Turn8]
                                              ↑ cut point (保留最近4个turn)
压缩后:    [CompactionSummary#1] [Turn5] [Turn6] [Turn7] [Turn8]

再次压缩（会话继续到Turn12后）:
压缩前:    [CompactionSummary#1] [Turn5-12]
     ↑ cut point
压缩后:    [CompactionSummary#2] [Turn9] [Turn10] [Turn11] [Turn12]
```

**CompactionSummaryMessage 格式：**

```typescript
interface CompactionSummaryMessage {
  role: "compactionSummary";
  summary: string;       // 压缩后的摘要文本
  tokensBefore: number;  // 压缩前 token 数（用于审计）
  timestamp: number;
}
```

**文件截断策略（`truncateAfterCompaction: true`）：**

压缩后直接重写 JSONL 文件，只保留：
1. 文件头（SessionHeader）
2. 摘要消息（CompactionSummaryMessage）
3. 保留的最近消息

避免文件无限增长，支持长时间运行的多轮压缩。

### 3.6 压缩流程完整伪代码

```
FUNCTION runCompaction(sessionFile, settings):
    1. 读取 session.jsonl 所有 entries

    2. IF entries.length <= MIN_ENTRIES:
           RETURN  // 历史太短，不需要压缩

    3. contextTokens = estimateContextTokens(entries)
    4. contextWindow = getModelContextWindow(session.model)

    5. IF NOT shouldCompact(contextTokens, contextWindow, settings):
           RETURN  // 未达到触发条件

    6. preparation = prepareCompaction(entries, settings)
    7. IF preparation IS EMPTY:
           RETURN  // 无法找到有效 cut point

    8. IF settings.memoryFlush:
           await runMemoryFlush()  // 预压缩 memory 持久化

    9. previousSummary = getLatestCompactionSummary(entries)
    10. summary = await generateSummary(
            preparation.messagesToSummarize,
            session.model,
            settings,
            previousSummary,
            customInstructions
        )

    11. compactionEntry = {
            type: "compactionSummary",
            summary,
            tokensBefore: preparation.tokensBefore,
            timestamp: NOW()
        }

    12. 追加 compactionEntry 到 session.jsonl

    13. IF settings.truncateAfterCompaction:
            rewriteSessionFile(entries, compactionEntry,
                               preparation.firstKeptEntryIndex)

    14. IF settings.postIndexSync == "await":
            await runMemoryReindex()
        ELIF settings.postIndexSync == "async":
            runMemoryReindex()  // 不等待

    15. 重载 session 到内存

    RETURN { summary, entriesRemoved: preparation.messagesToSummarize.length }
```

### 3.7 质量保障

**`qualityGuard` 配置：**

```typescript
interface QualityGuard {
  enabled: boolean;       // 默认 false
  maxRetries: number;     // 默认 2
}
```

**校验逻辑：**
1. 摘要生成后，检查摘要 token 数是否在合理范围（不超过原始的 20%）
2. 如果启用 `qualityGuard`，摘要需要经过二次校验 prompt 确认完整性
3. 校验失败则重试（最多 `maxRetries` 次）
4. 重试仍失败时，保留原始消息，不执行截断（fail-safe）

---

## 4. 实施建议

### 4.1 分阶段实施

**Phase 1 — 核心机制（优先）：**
- 实现 `estimateTokens()` / `calculateContextTokens()`
- 实现 `shouldCompact()` 触发判断
- 实现 `findCutPoint()` 切割点查找
- 实现压缩流程主循环

**Phase 2 — 摘要生成：**
- 实现 `generateSummary()` LLM 调用
- 支持 `previousSummary` 链式合并
- 集成到 OpenClaw 的 chat loop

**Phase 3 — 文件治理：**
- 实现 `truncateAfterCompaction` 文件重写
- 实现压缩历史可追溯性（`CompactionSummaryMessage` 链）
- 支持多轮压缩不退化

**Phase 4 — 质量与调优：**
- 实现 `qualityGuard` 校验
- 实现 `postIndexSync` memory 联动
- 暴露 metrics（压缩次数、token 节省比例）

### 4.2 实现位置

```
src/
  core/
    session/
      session-manager.ts   # Session 文件读写
      session-types.ts     # 消息类型定义
  compaction/
    index.ts              # 导出入口
    compaction.ts         # 核心压缩逻辑（pure functions）
    summarization.ts      # 摘要生成
    utils.ts              # 工具函数（estimateTokens 等）
  runtime/
    session-compaction.runtime.ts  # OpenClaw 集成层
```

### 4.3 OpenClaw 配置 schema 扩展

在现有 `agents.defaults.compaction` 基础上直接扩展，无需新建配置域。

### 4.4 Fail-Safe 设计

- **校验失败不截断**：摘要生成失败时不修改 session 文件
- **最小保留**：`recentTurnsPreserve` 始终保证最近轮次原文可见
- **超时中断**：`timeoutSeconds` 防止 LLM 调用挂起
- **幂等追加**：`CompactionSummaryMessage` 追加写入，失败可重试

### 4.5 与现有 pi-coding-agent 压缩的关系

OpenClaw 直接复用 `@mariozechner/pi-coding-agent` 的 `compaction/` 模块，不需要重新实现核心算法。主要工作在集成层：

- 将 OpenClaw 的 Session 格式映射到 pi-coding-agent 的 `SessionEntry[]`
- 处理 OpenClaw 特有的消息类型（如 Feishu 消息）
- 适配 OpenClaw 的配置 schema

---

## 5. 配置示例

```yaml
agents:
  defaults:
    compaction:
      enabled: true
      reserveTokens: 10000        # 保留 10k token 给生成用
      keepRecentTokens: 4000      # 保留最近 ~4k token 不压缩
      reserveTokensFloor: 5000    # 至少保留 5k token
      maxHistoryShare: 0.7        # 历史最多占上下文 70%
      recentTurnsPreserve: 3      # 最近 3 个完整 turn 原文保留
      timeoutSeconds: 900         # 压缩超时 15 分钟
      truncateAfterCompaction: false  # 暂不重写文件，保持可审计
      postIndexSync: "async"      # 异步 reindex，不阻塞压缩
      model: null                # 使用 session 主模型
```

---

## 6. 风险与限制

| 风险 | 缓解方案 |
|------|---------|
| 摘要丢失关键上下文 | 启用 `qualityGuard`，保留原文截断失败时回退 |
| LLM 摘要调用超时 | `timeoutSeconds` 保底；失败不截断文件 |
| 多次压缩后摘要膨胀 | `maxHistoryShare` 限制历史比例；链式合并控制大小 |
| 特殊消息类型（图片、工具调用）被错误摘要 | `estimateTokens` 对工具调用消息做额外 token 估算 |
| 文件系统写入冲突 | SessionManager 的 append 原子写入保证 |

---

## 7. 参考

- pi-coding-agent `compaction/` 模块源码：
  `node_modules/@mariozechner/pi-coding-agent/dist/core/compaction/`
- Session 文件格式：`docs/session.md`
- OpenClaw `runtime-schema.ts` 中的 `agents.defaults.compaction` 配置定义
