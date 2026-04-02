# OpenClaw exec 工具增强设计方案

## 1. OpenClaw exec 当前实现分析

### 1.1 核心文件位置

| 文件 | 职责 |
|------|------|
| `dist/model-runtime-BkEknIPR.js` | exec 工具 schema 定义 (`execSchema`)、`runExecProcess`、会话管理 |
| `dist/exec-NliLe8k-.js` | 底层进程执行：`runCommandWithTimeout`、`runExec`、`spawnWithFallback` |
| `dist/execAsync-Cl2CAOAJ.js` | 异步 exec 封装 |
| `dist/exec-approvals-*.js` | exec 审批流程 |
| `dist/openclaw-exec-env-D-qcr6HX.js` | exec 环境变量处理 |

### 1.2 当前 execSchema（行 1089-1102）

```typescript
const execSchema = Type.Object({
  command: Type.String({ description: "Shell command to execute" }),
  workdir: Type.Optional(Type.String({ description: "Working directory (defaults to cwd)" })),
  env: Type.Optional(Type.Record(Type.String(), Type.String())),
  yieldMs: Type.Optional(Type.Number({ description: "Milliseconds to wait before backgrounding (default 10000)" })),
  background: Type.Optional(Type.Boolean({ description: "Run in background immediately" })),
  timeout: Type.Optional(Type.Number({ description: "Timeout in seconds (optional, kills process on expiry)" })),
  pty: Type.Optional(Type.Boolean({ description: "Run in a pseudo-terminal (PTY) when available" })),
  elevated: Type.Optional(Type.Boolean({ description: "Run on the host with elevated permissions" })),
  host: Type.Optional(Type.String({ description: "Exec host/target (auto|sandbox|gateway|node)" })),
  security: Type.Optional(Type.String({ description: "Exec security mode (deny|allowlist|full)" })),
  ask: Type.Optional(Type.String({ description: "Exec ask mode (off|on-miss|always)" })),
  node: Type.Optional(Type.String({ description: "Node id/name for host=node" }))
});
```

### 1.3 当前已有特性

| 特性 | 状态 | 说明 |
|------|------|------|
| `timeout` | ✅ 已有 | 单位是**秒**，内部转换为毫秒传给 `runCommandWithTimeout` |
| `background` | ✅ 已有 | 通过 `yieldMs` + `background` 组合实现后台执行 |
| `yieldMs` | ✅ 已有 | 等待毫秒数后转入后台 |
| `termination` | ✅ 已有 | 返回 `timeout`/`no-output-timeout`/`signal`/`exit` |

### 1.4 当前输出处理

- `DEFAULT_MAX_OUTPUT = 2e5`（20万字符）
- `tail(session.aggregated, 2000)` - 结果只保留尾部 2000 字符
- 超过 `maxOutputChars` 时 `session.truncated = true`
- **没有**持久化到文件的功能

---

## 2. 增强功能设计方案

### 2.1 超时处理增强

#### 需求
```typescript
exec({
  command: "sleep 10",
  timeout: 5000  // 毫秒（注意：当前是秒）
})
// 返回 { interrupted: true, termination: "timeout", ... }
```

#### 设计方案

**改动点**：将 `timeout` 参数单位从**秒**改为**毫秒**（或新增 `timeoutMs` 参数）。

> ⚠️ **破坏性变更警告**：当前 `timeout` 是秒单位。改为毫秒会破坏向后兼容。
> 
> **推荐方案**：保留 `timeout`（秒），新增 `timeoutMs`（毫秒），优先级 `timeoutMs > timeout`。

```typescript
// 修改 execSchema
timeout: Type.Optional(Type.Number({ 
  description: "Timeout in milliseconds (optional, kills process on expiry)" 
})),
timeoutMs: Type.Optional(Type.Number({ 
  description: "Timeout in milliseconds (overrides timeout if both set)" 
})),

// 修改 runExecProcess 中的超时处理
const effectiveTimeoutMs = opts.timeoutMs ?? (typeof opts.timeoutSec === 'number' ? opts.timeoutSec * 1000 : void 0);
```

**响应字段增强**：
```typescript
// 在 buildExecExitOutcome 中增加 interrupted 字段
return {
  status: outcome.status,
  exitCode: outcome.exitCode,
  interrupted: outcome.status === 'failed' && (outcome.timedOut || outcome.noOutputTimedOut),
  termination: outcome.status === 'failed' ? classifyFailureKind(...) : 'exit',
  // ... 其他现有字段
};
```

---

### 2.2 后台任务增强

#### 需求
```typescript
exec({
  command: "python server.py",
  run_in_background: true
})
// 返回 { background_task_id: "xxx", ... }
```

#### 设计方案

**改动点**：增强 `background` 响应，返回 `background_task_id`。

当前 `runExecProcess` 已经支持 `background: true` 和 `yieldMs`，但返回的 session 中没有 `background_task_id` 字段。

```typescript
// 修改 execSchema - 添加描述说明
background: Type.Optional(Type.Boolean({ 
  description: "Run in background immediately. Returns background_task_id in response." 
})),

// 修改 runExecProcess 返回值
const result = {
  sessionId: session.id,
  background_task_id: session.backgrounded ? session.id : undefined,
  pid: session.pid,
  status: outcome.status,
  exitCode: outcome.exitCode,
  // ... 其他字段
};
```

**background_task_id 生成规则**：
使用现有的 `session.id`（格式如 `amber-reef-7kx`），或生成新的短 ID。

---

### 2.3 大输出持久化

#### 需求
```typescript
exec({
  command: "git log --all",
  max_output_size: 1024 * 1024  // 1MB 阈值
})
// 返回 { persisted_output_path: "/tmp/claw-output-xxx", ... }
```

#### 设计方案

**改动点**：
1. 新增 `max_output_size` 参数（字节数）
2. 输出超过阈值时写入临时文件
3. 返回 `persisted_output_path`

```typescript
// 修改 execSchema
max_output_size: Type.Optional(Type.Number({ 
  description: "Max output size in bytes. If exceeded, output is persisted to a temp file." 
})),

// 在 session 中新增字段
session: {
  // ... existing fields
  persistedOutputPath: void 0,
  persistedOutputWritten: false,
}

// 修改 appendOutput 函数
function appendOutput(session, stream, chunk) {
  const totalChars = session.pendingStdoutChars + session.pendingStderrChars;
  
  if (session.maxOutputChars && totalChars > session.maxOutputChars && !session.persistedOutputWritten) {
    // 开始持久化
    const tmpPath = `/tmp/claw-output-${session.id}-${Date.now()}.txt`;
    fsSync.writeFileSync(tmpPath, session.aggregated + chunk, 'utf8');
    session.persistedOutputPath = tmpPath;
    session.persistedOutputWritten = true;
    return;
  }
  
  if (session.persistedOutputWritten) {
    // 追加到文件
    fsSync.appendFileSync(session.persistedOutputPath, chunk, 'utf8');
    return;
  }
  
  // 正常累积
  session.pendingStdoutChars += chunk.length;
  session.aggregated += chunk;
  
  if (session.maxOutputChars && session.totalOutputChars > session.maxOutputChars) {
    session.truncated = true;
    session.aggregated = tail(session.aggregated, session.maxOutputChars);
  }
}
```

**默认阈值**：
- `DEFAULT_MAX_OUTPUT = 200000`（现有）
- 持久化阈值建议：`max_output_size` 默认 `2 * 1024 * 1024`（2MB），超过时持久化

**响应字段**：
```typescript
return {
  // ... existing fields
  persisted_output_path: session.persistedOutputPath,
  output_truncated: session.truncated,
};
```

---

### 2.4 路径规范化

#### 需求
- 在 `read`/`write`/`edit` 操作前规范化路径
- 防止 `../../../etc/passwd` 攻击
- 使用 `path.resolve()` 或 `fs.realpathSync()`

#### 设计方案

路径规范化主要在文件工具层实现（不在 exec 层）。但 exec 中也需要处理 `workdir` 参数。

```typescript
// 新增路径规范化工具函数
import path from 'node:path';
import fsSync from 'node:fs';

function normalizeAndValidatePath(inputPath, workspaceRoot) {
  // 1. 解析为绝对路径
  const absolutePath = path.isAbsolute(inputPath) 
    ? inputPath 
    : path.resolve(workspaceRoot, inputPath);
  
  // 2. 解析符号链接并获取真实路径
  let resolvedPath;
  try {
    resolvedPath = fsSync.realpathSync(absolutePath);
  } catch {
    resolvedPath = absolutePath;
  }
  
  // 3. 验证是否在 workspace 内
  const normalizedRoot = fsSync.realpathSync(workspaceRoot);
  if (!resolvedPath.startsWith(normalizedRoot + path.sep)) {
    throw new Error(`Path ${inputPath} resolves outside workspace`);
  }
  
  return resolvedPath;
}

// 在 runExecProcess 中处理 workdir
const normalizedWorkdir = opts.workdir 
  ? normalizeAndValidatePath(opts.workdir, workspaceRoot)
  : void 0;
```

**防护措施**：
1. `path.resolve()` 解析 `../` 和符号链接
2. `fs.realpathSync()` 处理符号链接逃逸
3. 验证解析后路径在 workspace 内

---

## 3. 实现代码片段

### 3.1 修改后的 execSchema

```typescript
const execSchema = Type.Object({
  command: Type.String({ description: "Shell command to execute" }),
  workdir: Type.Optional(Type.String({ description: "Working directory (defaults to cwd)" })),
  env: Type.Optional(Type.Record(Type.String(), Type.String())),
  yieldMs: Type.Optional(Type.Number({ description: "Milliseconds to wait before backgrounding (default 10000)" })),
  background: Type.Optional(Type.Boolean({ description: "Run in background immediately. Returns background_task_id in response." })),
  timeout: Type.Optional(Type.Number({ description: "Timeout in seconds (deprecated, use timeoutMs)" })),
  timeoutMs: Type.Optional(Type.Number({ description: "Timeout in milliseconds (overrides timeout if both set)" })),
  pty: Type.Optional(Type.Boolean({ description: "Run in a pseudo-terminal (PTY) when available" })),
  elevated: Type.Optional(Type.Boolean({ description: "Run on the host with elevated permissions" })),
  host: Type.Optional(Type.String({ description: "Exec host/target (auto|sandbox|gateway|node)" })),
  security: Type.Optional(Type.String({ description: "Exec security mode (deny|allowlist|full)" })),
  ask: Type.Optional(Type.String({ description: "Exec ask mode (off|on-miss|always)" })),
  node: Type.Optional(Type.String({ description: "Node id/name for host=node" })),
  max_output_size: Type.Optional(Type.Number({ description: "Max output size in bytes before persisting to temp file" })),
  maxOutput: Type.Optional(Type.Number({ description: "Max output characters to retain in memory (truncates tail)" }))
});
```

### 3.2 增强的 runExecProcess（核心改动）

```typescript
async function runExecProcess(opts) {
  const startedAt = Date.now();
  const sessionId = createSessionSlug();
  
  // 路径规范化（如果配置了 workspace）
  let normalizedWorkdir = opts.workdir;
  if (opts.workdir && opts.workspaceRoot) {
    normalizedWorkdir = normalizeAndValidatePath(opts.workdir, opts.workspaceRoot);
  }
  
  // 超时处理：优先使用 timeoutMs，否则转换 timeout（秒→毫秒）
  const effectiveTimeoutMs = opts.timeoutMs ?? (
    typeof opts.timeoutSec === 'number' 
      ? opts.timeoutSec * 1000 
      : void 0
  );
  
  // maxOutput 默认值
  const effectiveMaxOutput = opts.maxOutput ?? DEFAULT_MAX_OUTPUT;
  
  // max_output_size 持久化阈值
  const persistThreshold = opts.max_output_size ?? (2 * 1024 * 1024); // 默认 2MB
  
  const session = {
    id: sessionId,
    command: opts.command,
    // ... existing fields
    cwd: normalizedWorkdir,
    maxOutputChars: effectiveMaxOutput,
    persistThreshold,
    persistedOutputPath: void 0,
    persistedOutputWritten: false,
    background_task_id: void 0,
  };
  
  // 如果是后台任务，生成 background_task_id
  if (opts.background || (opts.yieldMs === 0)) {
    session.background_task_id = sessionId;
    session.backgrounded = true;
  }
  
  // ... spawn logic ...
  
  // 修改后的 appendOutput
  const appendOutput = (session, stream, chunk) => {
    const totalChars = session.pendingStdoutChars + session.pendingStderrChars;
    const fullSize = Buffer.byteLength(session.aggregated + chunk, 'utf8');
    
    // 检查是否需要开始持久化
    if (fullSize > session.persistThreshold && !session.persistedOutputWritten) {
      const tmpPath = `/tmp/claw-output-${session.id}.txt`;
      fsSync.writeFileSync(tmpPath, session.aggregated + chunk, 'utf8');
      session.persistedOutputPath = tmpPath;
      session.persistedOutputWritten = true;
      return;
    }
    
    if (session.persistedOutputWritten) {
      fsSync.appendFileSync(session.persistedOutputPath, chunk, 'utf8');
      return;
    }
    
    session.pendingStdoutChars += chunk.length;
    session.aggregated += chunk;
    
    // 内存中截断
    if (Buffer.byteLength(session.aggregated, 'utf8') > session.maxOutputChars) {
      session.truncated = true;
      session.aggregated = tail(session.aggregated, session.maxOutputChars);
    }
  };
  
  // ... rest of implementation ...
  
  return {
    sessionId,
    background_task_id: session.background_task_id,
    pid: session.pid,
    status: outcome.status,
    exitCode: outcome.exitCode,
    interrupted: outcome.timedOut || outcome.noOutputTimedOut,
    termination: outcome.termination,
    stdout: session.persistedOutputWritten ? '' : session.aggregated,
    stderr: '',
    persisted_output_path: session.persistedOutputPath,
    output_truncated: session.truncated,
    signal: outcome.exitSignal,
    killed: outcome.killed,
    durationMs: Date.now() - startedAt,
  };
}
```

### 3.3 路径规范化函数

```typescript
import path from 'node:path';
import fsSync from 'node:fs';

/**
 * 规范化并验证路径，防止 path traversal 攻击
 */
function normalizeAndValidatePath(inputPath, workspaceRoot, allowSymlinks = false) {
  // 1. 解析相对路径为绝对路径
  const absolutePath = path.isAbsolute(inputPath)
    ? inputPath
    : path.resolve(workspaceRoot, inputPath);
  
  // 2. 规范化路径（解析 .. 和 .）
  const normalizedPath = path.normalize(absolutePath);
  
  // 3. 处理符号链接（可选）
  let resolvedPath;
  if (allowSymlinks) {
    try {
      resolvedPath = fsSync.realpathSync(normalizedPath);
    } catch {
      resolvedPath = normalizedPath;
    }
  } else {
    resolvedPath = normalizedPath;
  }
  
  // 4. 验证路径在 workspace 内
  const normalizedRoot = allowSymlinks 
    ? fsSync.realpathSync(workspaceRoot) 
    : path.normalize(workspaceRoot);
  
  const isInsideWorkspace = 
    resolvedPath === normalizedRoot ||
    resolvedPath.startsWith(normalizedRoot + path.sep);
  
  if (!isInsideWorkspace) {
    throw new Error(
      `Path traversal attempt detected: "${inputPath}" resolves to ` +
      `"${resolvedPath}" which is outside workspace "${normalizedRoot}"`
    );
  }
  
  return resolvedPath;
}
```

---

## 4. 兼容性考虑

### 4.1 向后兼容策略

| 变更 | 兼容策略 |
|------|---------|
| `timeout` 参数 | 保留现有语义（秒），新增 `timeoutMs`（毫秒）供精确控制 |
| `background` 响应 | 新增 `background_task_id` 字段，不改变现有返回结构 |
| `max_output_size` | 新增参数，不影响现有行为 |
| 路径规范化 | 仅在提供了 `workspaceRoot` 配置时启用 |

### 4.2 破坏性变更清单

以下变更会破坏向后兼容，需要 major version 迭代：

1. ⚠️ `timeout` 从秒改为毫秒（**强烈不推荐**）
2. ⚠️ 移除 `yieldMs` 参数（已有替代方案）

### 4.3 配置项建议

```typescript
// openclaw.json 配置
{
  "tools": {
    "exec": {
      "timeout": {
        "default": 600,      // 默认 10 分钟
        "max": 3600          // 最大 1 小时
      },
      "max_output_size": {
        "default": 2 * 1024 * 1024,  // 2MB
        "persist_threshold": 5 * 1024 * 1024  // 超过 5MB 才持久化
      },
      "path_normalization": {
        "enabled": true,
        "allow_symlinks": false
      }
    }
  }
}
```

---

## 5. 实施优先级

| 优先级 | 功能 | 复杂度 | 风险 |
|--------|------|--------|------|
| P0 | `timeoutMs` 参数 | 低 | 无 |
| P0 | `background_task_id` 响应字段 | 低 | 无 |
| P1 | `max_output_size` + 持久化 | 中 | 中（涉及文件系统） |
| P1 | 路径规范化 | 中 | 低（仅新增验证） |
| P2 | `interrupted` 响应字段 | 低 | 无 |

---

## 6. 参考：claw-code Bash 工具特性

（需补充 claw-code 的具体实现细节以完成对比分析）
