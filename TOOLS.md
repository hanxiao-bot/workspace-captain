# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.

## Model Registry（模型注册表）

| Alias | Actual Model | Provider | API Type |
|-------|-------------|----------|----------|
| minimax-m2 | minimax-portal/MiniMax-M2 | volcengine | OpenAI |
| minimax-m2.1 | minimax-portal/MiniMax-M2.1 | volcengine | OpenAI |
| minimax-m2.5 | minimax-portal/MiniMax-M2.5 | volcengine | OpenAI |
| glm-4 | glm-4-0520 | volcengine | OpenAI |
| glm-4.5 | glm-4-0520 | volcengine | OpenAI |
| deepseek | deepseek-chat | volcengine | OpenAI |
| kimi | moonshot-v1-128k | volcengine | OpenAI |
| claude | claude-sonnet-4-6 | anthropic | Anthropic |
| gpt-4o | gpt-4o | openai | OpenAI |
| o3 | o3 | openai | OpenAI |
| o3-mini | o3-mini | openai | OpenAI |
| o4-mini | o4-mini | openai | OpenAI |

## Provider Configuration Templates

```json5
// volcengine (火山方舟) - 推荐
{
  "models": {
    "providers": {
      "volcengine": {
        "apiKey": "${VOLCENGINE_API_KEY}",
        "baseUrl": "https://ark.cn-beijing.volces.com/api/v3",
        "timeout": 120
      }
    }
  }
}

// anthropic
{
  "models": {
    "providers": {
      "anthropic": {
        "apiKey": "${ANTHROPIC_API_KEY}",
        "baseUrl": "https://api.anthropic.com"
      }
    }
  }
}

// openai
{
  "models": {
    "providers": {
      "openai": {
        "apiKey": "${OPENAI_API_KEY}",
        "baseUrl": "https://api.openai.com/v1"
      }
    }
  }
}
```

## 模型选择指南

- 代码任务：ollama/deepseek-r1:70b（本地）
- 文档任务：ollama/qwen3:14b（本地）
- 复杂推理：ollama/qwq:32b（本地）
- 云端默认：volcengine volcengine-plan

## Tool Policy（工具策略）

### 子Agent 工具约束

OpenClaw 支持细粒度工具控制，通过 `tools.subagents.tools` 配置：

```json5
{
  "tools": {
    "subagents": {
      "tools": {
        // 子Agent 允许的工具
        "allow": ["read", "write", "edit", "exec", "process"],
        // 子Agent 禁止的工具
        "deny": ["gateway", "cron", "browser", "nodes", "canvas"]
      }
    }
  }
}
```

### 危险工具说明

| 工具 | 风险 | 默认策略 |
|------|------|---------|
| exec | 可执行任意命令 | sandbox 模式下受限 |
| write/edit | 可修改文件 | 受 path boundary 限制 |
| gateway | 可重启/修改 OpenClaw | 默认禁止 |
| cron | 可创建定时任务 | 默认禁止 |
| browser/canvas | 可控制浏览器 | 默认禁止 |
| nodes | 可管理设备节点 | 默认禁止 |

### Path Boundary（路径边界）

所有文件操作受 workspace 边界限制：
- `read` 无法读取 workspace 外文件
- `write/edit` 无法写入 workspace 外文件
- `../` 逃逸被 lexical + canonical 双重检查阻止
- symlink 逃逸被检测并阻止

### Elevated 权限

需要 elevated 权限时：
```json5
{
  "tools": {
    "elevated": {
      "enabled": true,
      "allowFrom": ["discord:123456", "*"]
    }
  }
}
```

### Shell 安全

exec 工具过滤危险字符：
- 阻断：`;&|\`$<>` `'` `"` `\r` `\n`
- 路径参数白名单
- 禁止 flag 注入（`-` 开头参数）

## Tool Schema（工具输入参数）

OpenClaw 工具输入参数的 JSON Schema 参考：

### read
```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string", "description": "文件路径（绝对或相对）" },
    "offset": { "type": "integer", "minimum": 1, "description": "起始行号" },
    "limit": { "type": "integer", "minimum": 1, "description": "最大行数" }
  },
  "required": ["path"]
}
```

### write
```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string", "description": "文件路径" },
    "content": { "type": "string", "description": "文件内容" },
    "filePath": { "type": "string", "description": "文件路径（别名）" }
  },
  "required": ["path", "content"]
}
```

### edit
```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string", "description": "文件路径" },
    "oldText": { "type": "string", "description": "要替换的精确文本" },
    "newText": { "type": "string", "description": "替换后的文本" },
    "filePath": { "type": "string", "description": "文件路径（别名）" }
  },
  "required": ["path", "oldText", "newText"]
}
```

### exec
```json
{
  "type": "object",
  "properties": {
    "command": { "type": "string", "description": "要执行的命令" },
    "timeout": { "type": "integer", "minimum": 1, "description": "超时秒数" },
    "workdir": { "type": "string", "description": "工作目录" },
    "elevated": { "type": "boolean", "description": "是否使用 elevated 权限" }
  },
  "required": ["command"]
}
```

### process
```json
{
  "type": "object",
  "properties": {
    "action": { "type": "string", "enum": ["list", "poll", "log", "kill"], "description": "操作" },
    "sessionId": { "type": "string", "description": "会话 ID" },
    "data": { "type": "string", "description": "写入数据" }
  },
  "required": ["action"]
}
```

### sessions_spawn
```json
{
  "type": "object",
  "properties": {
    "task": { "type": "string", "description": "任务描述" },
    "label": { "type": "string", "description": "标签" },
    "runtime": { "type": "string", "enum": ["subagent", "acp"], "description": "运行时" },
    "mode": { "type": "string", "enum": ["run", "session"], "description": "模式" },
    "model": { "type": "string", "description": "模型覆盖" },
    "cleanup": { "type": "string", "enum": ["delete", "keep"], "description": "清理策略" },
    "runTimeoutSeconds": { "type": "integer", "description": "超时秒数" }
  },
  "required": ["task"]
}
```

## Sandbox 安全模型

### 模式

```json5
{
  "agents": {
    "defaults": {
      "sandbox": {
        "mode": "non-main"  // off | all | non-main
      }
    }
  }
}
```

| 模式 | 说明 |
|------|------|
| off | 无沙箱，exec 直接在宿主机执行 |
| all | 所有会话都沙箱化 |
| non-main | 仅子Agent沙箱，主会话不沙箱 |

### Docker 沙箱配置

沙箱使用 Docker 容器：

```json5
{
  "agents": {
    "list": [{
      "id": "main",
      "sandbox": {
        "mode": "non-main",
        "scope": "session"
      }
    }]
  }
}
```

Docker 容器限制：
- 网络：`network: "none"`（无网络）
- 能力：`capDrop: ["ALL"]`（移除所有 Linux capabilities）
- 文件系统：`readOnlyRoot: true`（只读根目录）
- 临时目录：`tmpfs: ["/tmp", "/var/tmp", "/run"]`

### Workspace 访问级别

```json5
{
  "sandbox": {
    "workspaceAccess": "rw"  // none | r | rw
  }
}
```

| 级别 | 读 | 写 |
|------|---|---|
| none | ❌ | ❌ |
| r | ✅ | ❌ |
| rw | ✅ | ✅ |

### Elevated 权限

需要绕过沙箱限制时：

```json5
{
  "tools": {
    "elevated": {
      "enabled": true,
      "allowFrom": ["feishu:ou_xxx", "*"]
    }
  }
}
```
