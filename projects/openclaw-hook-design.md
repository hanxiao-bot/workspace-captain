# OpenClaw Tool Hook 系统设计

> 参考：claw-code PreToolUse / PostToolUse Hook 系统
> 版本：v1.0 | 日期：2026-04-02

---

## 1. 背景与目标

### 1.1 现状

OpenClaw 目前已有**内部事件 Hook 系统**（`internal-hooks-BsNSP1Xa.js`）和**外部 Hook 执行器**（`hook-runtime-DQg-mC28.js`、`hook-runner-global-BJtjs6Ma.js`），支持以命令形式运行外部脚本。但缺少 **Tool 级别的 PreToolUse / PostToolUse 拦截能力**。

claw-code（Rust 版）已有成熟的 PreToolUse / PostToolUse Hook 实现，可直接借鉴。

### 1.2 目标

在 OpenClaw 工具执行链路中插入 Hook 拦截点，支持：

- **PreToolUse**：工具执行前拦截，可 Allow / Deny / Warn
- **PostToolUse**：工具执行后拦截，用于日志、审计、告警
- **外部命令调用**：退出码 0=Allow、2=Deny、其他=Warn
- **JSON payload 通过 stdin 传递**，stdout 捕获为消息

---

## 2. OpenClaw 工具执行入口分析

### 2.1 工具执行链路

```
LLM 决策
  → tool-send (工具发送/路由)
  → openclaw-tools.runtime (工具注册表)
  → tool-policy (策略检查)
  → [Hook 拦截点] ← 插入位置
  → exec / read / write / browser 等具体工具实现
  → 返回结果
```

### 2.2 关键文件

| 文件 | 职责 |
|------|------|
| `tool-send-Bj51u5jr.js` | 工具调用分发入口 |
| `openclaw-tools.runtime-DzsP9Qxw.js` | 工具注册与解析 |
| `tool-policy-DTveRWZi.js` | 工具访问策略（allow/deny） |
| `exec-NliLe8k-.js` | exec 工具底层实现（spawn/execFile） |
| `pi-tools.before-tool-call.runtime.js` | 循环检测（loop detection） |
| `hook-runtime-DQg-mC28.js` | 已有外部 Hook 运行时 |
| `hook-runner-global-BJtjs6Ma.js` | 已有全局 Hook 执行器 |

### 2.3 现有 Hook 执行机制

OpenClaw 已有完整的外部命令 Hook 基础设施（`hook-runner-global`）：

```javascript
// hook-runner-global-BJtjs6Ma.js 中的执行模式
const payload = JSON.stringify({
  hook_event_name: event.as_str(),
  tool_name,
  tool_input: parse_tool_input(tool_input),
  tool_input_json: tool_input,
  tool_output: tool_output,
  tool_result_is_error: is_error,
});

// 命令执行：stdin 传 payload，stdout 捕获消息
child.stdin(payload); // JSON via stdin
// exit code: 0 = allow, 2 = deny, 其他 = warn
```

**已有的能力可复用**，只需在工具执行入口处调用它。

### 2.4 插入点定位

Hook 拦截点应位于 **tool-policy 之后、具体工具实现之前**：

```
tool-send (路由)
  → tool-policy (allow/deny 策略)
  → [PreToolUse Hook 拦截点]     ← 新增
  → exec / read / write / ...
  → [PostToolUse Hook 拦截点]    ← 新增
  → 返回结果
```

---

## 3. Hook 系统设计

### 3.1 配置结构

```typescript
// config-schema 中新增
interface RuntimeHookConfig {
  pre_tool_use: string[];   // PreToolUse 命令列表
  post_tool_use: string[];  // PostToolUse 命令列表
}
```

```yaml
# openclaw.yaml
hooks:
  pre_tool_use:
    - "/usr/local/bin/openclaw-hook-pre.sh"
    - "python3 /opt/hook-audit.py"
  post_tool_use:
    - "/usr/local/bin/openclaw-hook-post.sh"
```

### 3.2 PreToolUse Hook

**触发时机**：工具执行前，policy 检查通过之后

**行为**：
- 执行 `pre_tool_use` 命令列表中的每个命令
- JSON payload 通过 stdin 传递
- stdout 输出作为附加消息
- 退出码处理：
  - `0` → **Allow**，工具正常执行
  - `2` → **Deny**，工具被拒绝执行，返回错误
  - **其他** → **Warn**，记录警告但仍允许执行

**Payload 格式（stdin）**：
```json
{
  "hook_event_name": "PreToolUse",
  "tool_name": "exec",
  "tool_input": { "command": "rm -rf /tmp/test" },
  "tool_input_json": "{\"command\":\"rm -rf /tmp/test\"}",
  "tool_output": null,
  "tool_result_is_error": false
}
```

**额外环境变量**：
```bash
HOOK_EVENT=PreToolUse
HOOK_TOOL_NAME=exec
HOOK_TOOL_INPUT={"command":"rm -rf /tmp/test"}
HOOK_TOOL_IS_ERROR=0
```

### 3.3 PostToolUse Hook

**触发时机**：工具执行完成（成功或失败）之后

**行为**：
- 执行 `post_tool_use` 命令列表中的每个命令
- JSON payload 通过 stdin 传递
- stdout 输出作为附加消息（不影响工具结果）
- 退出码不影响工具结果，统一记录 Warn

**Payload 格式（stdin）**：
```json
{
  "hook_event_name": "PostToolUse",
  "tool_name": "exec",
  "tool_input": { "command": "ls /tmp" },
  "tool_input_json": "{\"command\":\"ls /tmp\"}",
  "tool_output": "{\"stdout\":\"file1\\nfile2\",\"stderr\":\"\",\"code\":0}",
  "tool_result_is_error": false
}
```

### 3.4 Hook 执行器实现

参考 `hook-runtime-DQg-mC28.js` 中的现有实现：

```typescript
interface HookCommandOutcome {
  allowed: boolean;
  denied: boolean;
  message?: string;
}

interface HookResult {
  denied: boolean;
  messages: string[];
}

async function runHookCommands(
  commands: string[],
  event: 'PreToolUse' | 'PostToolUse',
  toolName: string,
  toolInput: string,
  toolOutput?: string,
  isError: boolean = false
): Promise<HookResult> {
  const payload = JSON.stringify({
    hook_event_name: event,
    tool_name: toolName,
    tool_input: parseToolInput(toolInput),
    tool_input_json: toolInput,
    tool_output: toolOutput ?? null,
    tool_result_is_error: isError,
  });

  const messages: string[] = [];

  for (const command of commands) {
    const outcome = await runSingleHookCommand(command, payload, {
      event,
      toolName,
      toolInput,
      toolOutput,
      isError,
    });

    if (outcome.denied) {
      return {
        denied: true,
        messages: [outcome.message ?? `${event} hook denied tool \`${toolName}\``],
      };
    }
    if (outcome.message) {
      messages.push(outcome.message);
    }
  }

  return { denied: false, messages };
}

async function runSingleHookCommand(
  command: string,
  payload: string,
  ctx: HookContext
): Promise<HookCommandOutcome> {
  return new Promise((resolve) => {
    const child = spawn('sh', ['-lc', command], {
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    child.stdin.write(payload);
    child.stdin.end();

    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (d) => { stdout += d.toString(); });
    child.stderr.on('data', (d) => { stderr += d.toString(); });

    child.on('close', (code) => {
      const msg = stdout.trim() || undefined;
      switch (code) {
        case 0:
          resolve({ allowed: true, denied: false, message: msg });
          break;
        case 2:
          resolve({ allowed: false, denied: true, message: msg });
          break;
        default:
          resolve({
            allowed: true,
            denied: false,
            message: `Hook exited ${code}; allowing: ${msg ?? stderr}`,
          });
      }
    });

    child.on('error', (err) => {
      resolve({
        allowed: true,
        denied: false,
        message: `Hook failed to start: ${err.message}`,
      });
    });
  });
}
```

---

## 4. 集成方案

### 4.1 新建 Hook 工具运行时模块

```
dist/
  tool-hooks.runtime-XxXxXxXx.js   # 新建：PreToolUse / PostToolUse Hook 执行器
```

```typescript
// tool-hooks.runtime.ts
import { runHookCommands } from './hook-runner-global.js';

export interface ToolHooksConfig {
  pre_tool_use: string[];
  post_tool_use: string[];
}

export async function runPreToolUseHooks(
  config: ToolHooksConfig,
  toolName: string,
  toolInput: string
): Promise<{ denied: boolean; messages: string[] }> {
  if (!config.pre_tool_use?.length) return { denied: false, messages: [] };
  return runHookCommands(config.pre_tool_use, 'PreToolUse', toolName, toolInput);
}

export async function runPostToolUseHooks(
  config: ToolHooksConfig,
  toolName: string,
  toolInput: string,
  toolOutput: string,
  isError: boolean
): Promise<{ denied: boolean; messages: string[] }> {
  if (!config.post_tool_use?.length) return { denied: false, messages: [] };
  return runHookCommands(config.post_tool_use, 'PostToolUse', toolName, toolInput, toolOutput, isError);
}
```

### 4.2 工具执行入口修改

在 `tool-send-Bj51u5jr.js` 或新建 `tool-dispatch.runtime.js` 中修改：

```typescript
// 伪代码：工具执行包装
async function invokeToolWithHooks(params: {
  toolName: string;
  toolInput: any;
  hookConfig: ToolHooksConfig;
  // ... 其他参数
}) {
  const { toolName, toolInput, hookConfig } = params;

  // 1. 执行 PreToolUse Hook
  const preResult = await runPreToolUseHooks(hookConfig, toolName, JSON.stringify(toolInput));
  if (preResult.denied) {
    return {
      ok: false,
      error: preResult.messages[0] ?? `Tool \`${toolName}\` denied by PreToolUse hook`,
      hookMessages: preResult.messages,
    };
  }

  // 2. 执行工具
  let toolResult;
  let toolError: Error | undefined;
  try {
    toolResult = await dispatchTool(toolName, toolInput);
  } catch (err) {
    toolError = err as Error;
  }

  // 3. 执行 PostToolUse Hook
  const isError = !!toolError;
  const postResult = await runPostToolUseHooks(
    hookConfig,
    toolName,
    JSON.stringify(toolInput),
    JSON.stringify(toolResult),
    isError
  );

  // 4. 返回结果（含 hook 消息）
  return {
    ok: !toolError,
    result: toolResult,
    error: toolError?.message,
    hookMessages: [...preResult.messages, ...postResult.messages],
  };
}
```

### 4.3 配置读取

在工具调用上下文构建时，从 `RuntimeConfig.hooks` 读取 Hook 配置，传递给 `invokeToolWithHooks`。

---

## 5. Hook 命令示例

### 5.1 PreToolUse: 危险命令拦截

```bash
#!/bin/bash
# hooks/pre-exec.sh
# 拒绝所有 rm -rf / 或涉及 /home 的危险操作

read -r PAYLOAD
TOOL_NAME=$(echo "$PAYLOAD" | jq -r '.tool_name')
TOOL_INPUT=$(echo "$PAYLOAD" | jq -r '.tool_input_json')

if [ "$TOOL_NAME" = "exec" ]; then
  COMMAND=$(echo "$TOOL_INPUT" | jq -r '.command // empty')
  if echo "$COMMAND" | grep -qE 'rm\s+-rf\s+/($|\s)'; then
    echo "Dangerous: rm -rf on root denied"
    exit 2  # Deny
  fi
fi

exit 0  # Allow
```

### 5.2 PostToolUse: 执行审计

```bash
#!/bin/bash
# hooks/post-audit.sh
# 记录所有工具执行到审计日志

read -r PAYLOAD
TIMESTAMP=$(date -Iseconds)
TOOL_NAME=$(echo "$PAYLOAD" | jq -r '.tool_name')
TOOL_INPUT=$(echo "$PAYLOAD" | jq -r '.tool_input_json')
TOOL_OUTPUT=$(echo "$PAYLOAD" | jq -r '.tool_output // empty')
IS_ERROR=$(echo "$PAYLOAD" | jq -r '.tool_result_is_error')

LOG_LINE="[$TIMESTAMP] $TOOL_NAME | input=$TOOL_INPUT | error=$IS_ERROR"

if [ "$IS_ERROR" = "true" ]; then
  echo "$LOG_LINE" >> /var/log/openclaw/hook-errors.log
else
  echo "$LOG_LINE" >> /var/log/openclaw/hook-audit.log
fi

exit 0
```

### 5.3 PreToolUse: 白名单模式

```python
#!/usr/bin/env python3
# hooks/pre-whitelist.py
# 只允许特定工具列表

import json, sys, os

allowed_tools = {"read", "write", "edit", "exec", "process", "web_fetch"}

payload = json.load(sys.stdin)
tool_name = payload.get("tool_name", "")

if tool_name not in allowed_tools:
    print(f"Tool '{tool_name}' not in whitelist")
    sys.exit(2)  # Deny

sys.exit(0)  # Allow
```

---

## 6. 实施建议

### 6.1 分阶段实施

| 阶段 | 内容 | 优先级 |
|------|------|--------|
| 1 | 新建 `tool-hooks.runtime.js`，复用 `hook-runner-global` 执行器 | P0 |
| 2 | 在 `tool-send` 工具执行入口注入 Pre/Post Hook 调用 | P0 |
| 3 | 配置 Schema 支持 (`runtime-schema`) | P1 |
| 4 | CLI 命令 `openclaw hooks list/run` 管理工具 | P2 |
| 5 | Hook 日志输出到 session 历史 | P2 |

### 6.2 关键设计决策

1. **同步执行**：Hook 同步执行，不异步（避免时序问题）
2. **短路逻辑**：PreToolUse Deny 时立即返回，不执行 PostToolUse
3. **超时控制**：Hook 命令应有 5s 超时，避免挂起主流程
4. **递归防护**：Hook 执行时不再触发 Hook（防递归）
5. **配置隔离**：Hook 配置属于 `RuntimeFeatureConfig`，不泄露到外部 channel 配置

### 6.3 性能考虑

- Hook 命令列表建议控制在 10 个以内
- 每个 Hook 超时 5s，全局超时 30s
- 可考虑 Hook 结果 LRU 缓存（针对幂等 PreToolUse）

---

## 7. 与 claw-code 的差异

| 特性 | claw-code (Rust) | OpenClaw (本设计) |
|------|-----------------|-------------------|
| 退出码 0 | Allow | Allow |
| 退出码 2 | Deny | Deny |
| 其他退出码 | Warn | Warn |
| stdin | JSON payload | JSON payload |
| 环境变量 | HOOK_EVENT 等 | 同 claw-code |
| 配置位置 | RuntimeFeatureConfig | RuntimeConfig.hooks |
| 工具执行包装 | 在 tools crate | 在 tool-send 分发层 |

---

## 8. 附录：相关文件索引

```
dist/
├── tool-send-Bj51u5jr.js              # 工具分发入口 [需修改]
├── openclaw-tools.runtime-DzsP9Qxw.js # 工具注册表
├── tool-policy-DTveRWZi.js            # 工具策略
├── hook-runtime-DQg-mC28.js           # Hook 运行时 [复用]
├── hook-runner-global-BJtjs6Ma.js      # 全局 Hook 执行器 [复用]
├── internal-hooks-BsNSP1Xa.js         # 内部事件 Hook 系统
├── pi-tools.before-tool-call.runtime.js # 循环检测
├── runtime-schema-B34T_6nr.js         # 配置 Schema [需修改]
└── exec-NliLe8k-.js                   # exec 工具实现
```

---

*设计完成，等待实施。*
