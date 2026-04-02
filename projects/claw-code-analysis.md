# claw-code 高价值特性深度分析报告

> 分析时间：2026-04-02  
> 项目位置：/Users/dc/.openclaw/workspace-captain/claw-code/  
> 分析范围：Rust 实现的核心模块

---

## 目录

1. [工具实现细节](#1-工具实现细节)
2. [Hook 系统](#2-hook-系统)
3. [MCP 实现](#3-mcp-实现)
4. [会话管理和压缩](#4-会话管理和压缩)
5. [权限系统](#5-权限系统)
6. [Git 工作流命令](#6-git-工作流命令)
7. [插件系统](#7-插件系统)
8. [优先级清单](#8-优先级清单)

---

## 1. 工具实现细节

### 1.1 工具注册与执行架构

claw-code 的工具系统采用**注册表模式**，通过 `GlobalToolRegistry` 统一管理内置工具和插件工具。

**核心数据结构（rust/crates/tools/src/lib.rs）：**

```rust
pub struct GlobalToolRegistry {
    plugin_tools: Vec<PluginTool>,
}

impl GlobalToolRegistry {
    // 内置工具名称规范化映射（alias -> canonical）
    // read -> read_file, write -> write_file, edit -> edit_file, glob -> glob_search, grep -> grep_search
    pub fn normalize_allowed_tools(&self, values: &[String]) -> Result<Option<BTreeSet<String>>, String>
    
    // 合并内置 + 插件工具定义
    pub fn definitions(&self, allowed_tools: Option<&BTreeSet<String>>) -> Vec<ToolDefinition>
    
    // 返回 (tool_name, required_permission) 列表
    pub fn permission_specs(&self, allowed_tools: Option<&BTreeSet<String>>) -> Vec<(String, PermissionMode)>
    
    // 执行工具：先查内置，再查插件
    pub fn execute(&self, name: &str, input: &Value) -> Result<String, String>
}
```

**工具调度入口：**

```rust
pub fn execute_tool(name: &str, input: &Value) -> Result<String, String> {
    match name {
        "bash" => from_value::<BashCommandInput>(input).and_then(run_bash),
        "read_file" => from_value::<ReadFileInput>(input).and_then(run_read_file),
        "write_file" => from_value::<WriteFileInput>(input).and_then(run_write_file),
        "edit_file" => from_value::<EditFileInput>(input).and_then(run_edit_file),
        "glob_search" => from_value::<GlobSearchInputValue>(input).and_then(run_glob_search),
        "grep_search" => from_value::<GrepSearchInput>(input).and_then(run_grep_search),
        "WebFetch" => from_value::<WebFetchInput>(input).and_then(run_web_fetch),
        "WebSearch" => from_value::<WebSearchInput>(input).and_then(run_web_search),
        // ...
        _ => Err(format!("unsupported tool: {name}")),
    }
}
```

### 1.2 Bash 工具实现

**BashCommandInput 结构（runtime/src/bash.rs）：**

```rust
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct BashCommandInput {
    pub command: String,
    pub timeout: Option<u64>,                    // 超时毫秒
    pub description: Option<String>,
    pub run_in_background: Option<bool>,         // 后台运行
    pub dangerously_disable_sandbox: Option<bool>,
    pub namespace_restrictions: Option<bool>,    // Linux namespace 隔离
    pub isolate_network: Option<bool>,           // 网络隔离
    pub filesystem_mode: Option<FilesystemIsolationMode>,  // 文件系统隔离模式
    pub allowed_mounts: Option<Vec<String>>,     // 允许挂载的目录
}
```

**BashCommandOutput 结构（关键字段）：**

```rust
pub struct BashCommandOutput {
    pub stdout: String,
    pub stderr: String,
    pub interrupted: bool,           // 是否超时中断
    pub background_task_id: Option<String>,  // 后台任务ID
    pub return_code_interpretation: Option<String>,  // 如 "exit_code:1" 或 "timeout"
    pub sandbox_status: Option<SandboxStatus>,  // 沙箱状态
    pub persisted_output_path: Option<String>,  // 大输出持久化路径
    pub persisted_output_size: Option<u64>,
    // ...
}
```

**异步执行流程（tokio）：**

```rust
async fn execute_bash_async(
    input: BashCommandInput,
    sandbox_status: SandboxStatus,
    cwd: std::path::PathBuf,
) -> io::Result<BashCommandOutput> {
    let mut command = prepare_tokio_command(&input.command, &cwd, &sandbox_status, true);

    let output_result = if let Some(timeout_ms) = input.timeout {
        match timeout(Duration::from_millis(timeout_ms), command.output()).await {
            Ok(result) => (result?, false),
            Err(_) => {
                return Ok(BashCommandOutput {
                    // 超时返回 interrupted=true
                    interrupted: true,
                    stderr: format!("Command exceeded timeout of {timeout_ms} ms"),
                    // ...
                });
            }
        }
    } else {
        (command.output().await?, false)
    };
    // ...
}
```

### 1.3 ReadFile/WriteFile/EditFile 实现

**核心实现（runtime/src/file_ops.rs）：**

```rust
pub fn read_file(
    path: &str,
    offset: Option<usize>,
    limit: Option<usize>,
) -> io::Result<ReadFileOutput> {
    let absolute_path = normalize_path(path)?;
    let content = fs::read_to_string(&absolute_path)?;
    let lines: Vec<&str> = content.lines().collect();
    let start_index = offset.unwrap_or(0).min(lines.len());
    let end_index = limit.map_or(lines.len(), |limit| {
        start_index.saturating_add(limit).min(lines.len())
    });
    let selected = lines[start_index..end_index].join("\n");

    Ok(ReadFileOutput {
        kind: String::from("text"),
        file: TextFilePayload {
            file_path: absolute_path.to_string_lossy().into_owned(),
            content: selected,
            num_lines: end_index.saturating_sub(start_index),
            start_line: start_index.saturating_add(1),  // 1-based 行号
            total_lines: lines.len(),
        },
    })
}
```

**write_file 的 Patch 生成：**

```rust
pub fn write_file(path: &str, content: &str) -> io::Result<WriteFileOutput> {
    let absolute_path = normalize_path_allow_missing(path)?;
    let original_file = fs::read_to_string(&absolute_path).ok();  // 读原文件（可能不存在）
    if let Some(parent) = absolute_path.parent() {
        fs::create_dir_all(parent)?;  // 自动创建父目录
    }
    fs::write(&absolute_path, content)?;

    Ok(WriteFileOutput {
        kind: if original_file.is_some() { "update" } else { "create" },
        structured_patch: make_patch(original_file.as_deref().unwrap_or(""), content),
        original_file,  // 保留原始内容
        git_diff: None,
        // ...
    })
}
```

**EditFile 的原子性替换：**

```rust
pub fn edit_file(
    path: &str,
    old_string: &str,
    new_string: &str,
    replace_all: bool,  // 是否全部替换
) -> io::Result<EditFileOutput> {
    let absolute_path = normalize_path(path)?;
    let original_file = fs::read_to_string(&absolute_path)?;
    
    // 安全检查：old_string 必须存在
    if !original_file.contains(old_string) {
        return Err(io::Error::new(
            io::ErrorKind::NotFound,
            "old_string not found in file",
        ));
    }

    let updated = if replace_all {
        original_file.replace(old_string, new_string)  // replace 全部
    } else {
        original_file.replacen(old_string, new_string, 1)  // replacen 只替换第一个
    };
    fs::write(&absolute_path, &updated)?;

    Ok(EditFileOutput {
        structured_patch: make_patch(&original_file, &updated),
        user_modified: false,
        replace_all,
        // ...
    })
}
```

### 1.4 GrepSearch 实现

```rust
pub fn grep_search(input: &GrepSearchInput) -> io::Result<GrepSearchOutput> {
    let regex = RegexBuilder::new(&input.pattern)
        .case_insensitive(input.case_insensitive.unwrap_or(false))
        .dot_matches_new_line(input.multiline.unwrap_or(false))
        .build()
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidInput, error.to_string()))?;

    // output_mode 支持: "files_with_matches"(默认) | "content" | "count"
    // 支持 glob 过滤、文件类型过滤、上下文行、limit/offset
    for file_path in collect_search_files(&base_path)? {
        let file_contents = fs::read_to_string(&file_path)?;
        let lines: Vec<&str> = file_contents.lines().collect();
        let mut matched_lines = Vec::new();
        for (index, line) in lines.iter().enumerate() {
            if regex.is_match(line) {
                matched_lines.push(index);
            }
        }
        if matched_lines.is_empty() { continue; }
        
        // content 模式输出带文件名和行号
        if output_mode == "content" {
            for index in matched_lines {
                let start = index.saturating_sub(context);
                let end = (index + context + 1).min(lines.len());
                content_lines.push(format!("{}:{}:{}", 
                    file_path.to_string_lossy(), current + 1, line));
            }
        }
    }
}
```

### 1.5 路径规范化

```rust
fn normalize_path(path: &str) -> io::Result<PathBuf> {
    let candidate = if Path::new(path).is_absolute() {
        PathBuf::from(path)
    } else {
        std::env::current_dir()?.join(path)
    };
    candidate.canonicalize()  // 解析 symlink，获取绝对路径
}

fn normalize_path_allow_missing(path: &str) -> io::Result<PathBuf> {
    // 与上面类似，但允许文件不存在（用于 write_file 创建新文件）
    if let Ok(canonical) = candidate.canonicalize() {
        return Ok(canonical);
    }
    // 文件不存在时，尝试 canonicalize 父目录 + 原文件名
    if let Some(parent) = candidate.parent() {
        let canonical_parent = parent.canonicalize().unwrap_or_else(|_| parent.to_path_buf());
        if let Some(name) = candidate.file_name() {
            return Ok(canonical_parent.join(name));
        }
    }
    Ok(candidate)
}
```

### 1.6 借鉴价值

| 特性 | 借鉴价值 | OpenClaw 实施建议 |
|------|----------|-------------------|
| 工具注册表 + 别名映射 | 高 | 在 tools 工具中实现 `normalizeToolName`，支持 `read` → `read_file` |
| Bash 后台任务 + TaskID | 高 | 扩展 exec 工具支持 `background: true`，返回 task ID |
| 大输出持久化到文件 | 高 | exec 输出超限时写入 tmp 文件， 返回 path |
| 文件操作的 structured_patch | 中 | edit/write 返回 unified diff 格式 |
| read_file offset/limit | 中 | read 工具支持 offset/limit 参数 |
| grep 支持 content/count/files 模式 | 中 | grep 工具增加 output_mode 参数 |

---

## 2. Hook 系统

### 2.1 Runtime Hook 系统（核心）

**Hook 事件定义（runtime/src/hooks.rs）：**

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HookEvent {
    PreToolUse,
    PostToolUse,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HookRunResult {
    denied: bool,
    messages: Vec<String>,
}

impl HookRunResult {
    pub fn allow(messages: Vec<String>) -> Self { Self { denied: false, messages } }
    pub fn is_denied(&self) -> bool { self.denied }
    pub fn messages(&self) -> &[String] { &self.messages }
}
```

**Hook 配置结构：**

```rust
pub struct RuntimeHookConfig {
    pre_tool_use: Vec<String>,   // shell 命令列表
    post_tool_use: Vec<String>,
}

pub struct HookRunner {
    config: RuntimeHookConfig,
}

impl HookRunner {
    pub fn run_pre_tool_use(&self, tool_name: &str, tool_input: &str) -> HookRunResult
    pub fn run_post_tool_use(&self, tool_name: &str, tool_input: &str, tool_output: &str, is_error: bool) -> HookRunResult
}
```

**Hook 执行引擎（关键）：**

```rust
fn run_commands(
    &self,
    event: HookEvent,
    commands: &[String],
    tool_name: &str,
    tool_input: &str,
    tool_output: Option<&str>,
    is_error: bool,
) -> HookRunResult {
    // 构造 JSON payload 通过 stdin 传给 hook
    let payload = json!({
        "hook_event_name": event.as_str(),
        "tool_name": tool_name,
        "tool_input": parse_tool_input(tool_input),   // 解析 JSON 或返回 {raw: string}
        "tool_input_json": tool_input,
        "tool_output": tool_output,
        "tool_result_is_error": is_error,
    }).to_string();

    // 每个 command 是一个独立的 shell 命令
    for command in commands {
        match Self::run_command(command, ...) {
            HookCommandOutcome::Allow { message } => { messages.push(message); }
            HookCommandOutcome::Deny { message } => { 
                // exit code 2 = deny，终止剩余 hooks
                return HookRunResult { denied: true, messages };
            }
            HookCommandOutcome::Warn { message } => { messages.push(message); }
        }
    }
    HookRunResult::allow(messages)
}
```

**Hook 命令的退出码语义：**

| 退出码 | 含义 |
|--------|------|
| 0 | Allow，stdout 作为 message 附加 |
| 2 | Deny，阻止工具执行 |
| 其他非0 | Warn，允许继续执行 |

**传递给 hook 的环境变量：**

```
HOOK_EVENT=PreToolUse|PostToolUse
HOOK_TOOL_NAME=Read
HOOK_TOOL_INPUT={"path":"README.md"}
HOOK_TOOL_INPUT_JSON={"path":"README.md"}
HOOK_TOOL_OUTPUT=<output string>
HOOK_TOOL_IS_ERROR=0|1
```

### 2.2 在 ConversationRuntime 中集成 Hook

**执行流程（runtime/src/conversation.rs）：**

```rust
// 工具执行主循环
for (tool_use_id, tool_name, input) in pending_tool_uses {
    // Step 1: 权限检查
    let permission_outcome = self.permission_policy.authorize(&tool_name, &input, prompter.as_mut());
    
    let result_message = match permission_outcome {
        PermissionOutcome::Allow => {
            // Step 2: PreToolUse Hook
            let pre_hook_result = self.hook_runner.run_pre_tool_use(&tool_name, &input);
            if pre_hook_result.is_denied() {
                // Hook 拒绝，返回错误结果
                ConversationMessage::tool_result(tool_use_id, tool_name, 
                    format_hook_message(&pre_hook_result, "PreToolUse hook denied"), true)
            } else {
                // Step 3: 实际执行工具
                let (mut output, mut is_error) = self.tool_executor.execute(&tool_name, &input)
                    .map(|o| (o, false))
                    .unwrap_or_else(|e| (e.to_string(), true));
                
                // 合并 pre hook 的 feedback 到 output
                output = merge_hook_feedback(pre_hook_result.messages(), output, false);
                
                // Step 4: PostToolUse Hook
                let post_hook_result = self.hook_runner.run_post_tool_use(
                    &tool_name, &input, &output, is_error);
                if post_hook_result.is_denied() { is_error = true; }
                output = merge_hook_feedback(post_hook_result.messages(), output, is_error);
                
                ConversationMessage::tool_result(tool_use_id, tool_name, output, is_error)
            }
        }
        PermissionOutcome::Deny { reason } => {
            ConversationMessage::tool_result(tool_use_id, tool_name, reason, true)
        }
    };
}
```

### 2.3 Plugin Hook 系统（plugins/src/hooks.rs）

插件系统的 Hook 与 Runtime Hook 几乎完全一致，但通过插件 manifest 注册：

```rust
// 插件 manifest 中的 hooks 配置
pub struct PluginHooks {
    #[serde(rename = "PreToolUse", default)]
    pub pre_tool_use: Vec<String>,
    #[serde(rename = "PostToolUse", default)]
    pub post_tool_use: Vec<String>,
}
```

**Plugin Hook 的聚合执行：**

```rust
impl PluginRegistry {
    pub fn aggregated_hooks(&self) -> Result<PluginHooks, PluginError> {
        self.plugins
            .iter()
            .filter(|plugin| plugin.is_enabled())
            .try_fold(PluginHooks::default(), |acc, plugin| {
                Ok(acc.merged_with(plugin.hooks()))  // 合并多个插件的 hooks
            })
    }
}
```

### 2.4 借鉴价值

| 特性 | 借鉴价值 | OpenClaw 实施建议 |
|------|----------|-------------------|
| 退出码 0/2/其他 = Allow/Deny/Warn | 高 | 在工具执行前/后支持 hook 命令 |
| stdin JSON payload 传递完整上下文 | 高 | hook 可解析工具名、输入、输出 |
| 多 hook 链式执行，短路终止 | 高 | 实现 pre_tool_use/post_tool_use 拦截点 |
| Hook feedback 合并到工具输出 | 中 | 工具结果附加 hook 输出 |

**OpenClaw 具体实现方案：**

```typescript
// hooks 配置文件格式 (yaml 或 json)
hooks:
  pre_tool_use:
    - command: "check_dangerous.sh"
      args: ["{tool_name}", "{tool_input}"]
  post_tool_use:
    - command: "log_tool.sh"

// 执行器
async function runHook(event: 'PreToolUse' | 'PostToolUse', tool: ToolCall): Promise<HookResult> {
  const payload = JSON.stringify({
    hook_event_name: event,
    tool_name: tool.name,
    tool_input: parseToolInput(tool.input),  // 尝试解析 JSON
    tool_input_json: JSON.stringify(tool.input),
    tool_output: tool.output,
    tool_result_is_error: tool.isError,
  });
  
  for (const hook of hooks[event]) {
    const result = await execWithStdin(hook.command, payload, hook.args);
    if (result.exitCode === 2) return { denied: true, message: result.stdout };
    if (result.exitCode !== 0) warnings.push(result.stdout);
    else if (result.stdout) messages.push(result.stdout);
  }
  return { denied: false, messages };
}
```

---

## 3. MCP 实现

### 3.1 MCP 工具命名规范

**工具名规范化（runtime/src/mcp.rs）：**

```rust
pub fn normalize_name_for_mcp(name: &str) -> String {
    let mut normalized = name
        .chars()
        .map(|ch| match ch {
            'a'..='z' | 'A'..='Z' | '0'..='9' | '_' | '-' => ch,
            _ => '_',  // 非字母数字下划线连字符，全部转为下划线
        })
        .collect::<String>();

    // 处理 "claude.ai Example   Server!!" -> "claude_ai_Example_Server"
    if name.starts_with(CLAUDEAI_SERVER_PREFIX) {
        normalized = collapse_underscores(&normalized)
            .trim_matches('_')
            .to_string();
    }
    normalized
}

// 工具名格式：mcp__<server_name>__<tool_name>
// 例如：mcp__github_com__create_issue
pub fn mcp_tool_name(server_name: &str, tool_name: &str) -> String {
    format!("{}{}", mcp_tool_prefix(server_name), normalize_name_for_mcp(tool_name))
}
```

### 3.2 MCP Server 配置签名

**Stdio Server 签名：**

```rust
fn render_command_signature(command: &[String]) -> String {
    let escaped = command
        .iter()
        .map(|part| part.replace('\\', "\\\\").replace('|', "\\|"))
        .collect::<Vec<_>>();
    format!("[{}]", escaped.join("|"))
    // 输出示例: [uvx|mcp-server]
}

fn scoped_mcp_config_hash(config: &ScopedMcpServerConfig) -> String {
    // Stdio: "stdio|<command>|<args>|<env>"
    // SSE/HTTP: "sse|<url>|<headers>|<oauth>"
    // 每个字段都纳入 hash，用于检测配置变化
    stable_hex_hash(&rendered)
}
```

**URL 解包（CCR Proxy 场景）：**

```rust
// Anthropic CCR 代理 URL 格式：
// https://api.anthropic.com/v2/ccr-sessions/1?mcp_url=wss%3A%2F%2Fvendor.example%2Fmcp
pub fn unwrap_ccr_proxy_url(url: &str) -> String {
    if !CCR_PROXY_PATH_MARKERS.iter().any(|marker| url.contains(marker)) {
        return url.to_string();  // 非代理 URL，原样返回
    }
    // 从 query string 中提取 mcp_url 参数
    for pair in query.split('&') {
        let mut parts = pair.splitn(2, '=');
        if matches!(parts.next(), Some("mcp_url")) {
            return percent_decode(parts.next()?);
        }
    }
    url.to_string()
}
```

### 3.3 MCP Client Transport

**Transport 类型（runtime/src/mcp_client.rs）：**

```rust
pub enum McpClientTransport {
    Stdio(McpStdioTransport),      // 本地子进程通过 stdin/stdout 通信
    Sse(McpRemoteTransport),      // SSE (Server-Sent Events)
    Http(McpRemoteTransport),     // HTTP
    WebSocket(McpRemoteTransport), // WebSocket
    Sdk(McpSdkTransport),         // SDK 方式
    ManagedProxy(McpManagedProxyTransport),  // Claude.ai 托管代理
}

pub enum McpClientAuth {
    None,
    OAuth(McpOAuthConfig),  // OAuth 认证
    Header(BTreeMap<String, String>),  // 自定义 header
}
```

### 3.4 借鉴价值

| 特性 | 借鉴价值 | OpenClaw 实施建议 |
|------|----------|-------------------|
| MCP 工具名规范化 | 高 | 实现 `normalizeToolName`，处理特殊字符 |
| Server 配置签名 + hash | 高 | 检测 MCP server 配置变化，热重载 |
| CCR Proxy URL 解包 | 中 | 支持 MCP over Claude.ai proxy 场景 |
| Transport 抽象（Stdio/SSE/WS） | 高 | 支持多种 MCP server 连接方式 |
| 配置哈希用于缓存/重载判断 | 高 | server fingerprinting |

---

## 4. 会话管理和压缩

### 4.1 Session 数据模型

**核心结构（runtime/src/session.rs）：**

```rust
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum MessageRole {
    System, User, Assistant, Tool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum ContentBlock {
    Text { text: String },
    ToolUse { id: String, name: String, input: String },
    ToolResult { tool_use_id: String, tool_name: String, output: String, is_error: bool },
}

pub struct ConversationMessage {
    pub role: MessageRole,
    pub blocks: Vec<ContentBlock>,
    pub usage: Option<TokenUsage>,
}

pub struct Session {
    pub version: u32,
    pub messages: Vec<ConversationMessage>,
}
```

**JSON 序列化/反序列化（自实现，非 serde derive）：**

```rust
impl Session {
    pub fn save_to_path(&self, path: impl AsRef<Path>) -> Result<(), SessionError> {
        fs::write(path, self.to_json().render())?;
        Ok(())
    }
    pub fn load_from_path(path: impl AsRef<Path>) -> Result<Self, SessionError> { /* ... */ }
    
    pub fn to_json(&self) -> JsonValue {
        let mut object = BTreeMap::new();
        object.insert("version".to_string(), JsonValue::Number(i64::from(self.version)));
        object.insert("messages".to_string(), JsonValue::Array(
            self.messages.iter().map(ConversationMessage::to_json).collect()
        ));
        JsonValue::Object(object)
    }
}
```

### 4.2 压缩算法详解

**压缩触发条件（runtime/src/compact.rs）：**

```rust
pub struct CompactionConfig {
    pub preserve_recent_messages: usize,  // 默认 4
    pub max_estimated_tokens: usize,       // 默认 10_000
}

pub fn should_compact(session: &Session, config: CompactionConfig) -> bool {
    // 跳过已有的压缩摘要前缀
    let compactable = &session.messages[compacted_summary_prefix_len(session)..];
    
    compactable.len() > config.preserve_recent_messages
        && compactable.iter().map(estimate_message_tokens).sum::<usize>() 
            >= config.max_estimated_tokens
}
```

**Token 估算（简单但有效）：**

```rust
fn estimate_message_tokens(message: &ConversationMessage) -> usize {
    message.blocks.iter().map(|block| match block {
        ContentBlock::Text { text } => text.len() / 4 + 1,  // 字符数 / 4
        ContentBlock::ToolUse { name, input, .. } => (name.len() + input.len()) / 4 + 1,
        ContentBlock::ToolResult { tool_name, output, .. } => 
            (tool_name.len() + output.len()) / 4 + 1,
    }).sum()
}
```

**压缩核心逻辑：**

```rust
pub fn compact_session(session: &Session, config: CompactionConfig) -> CompactionResult {
    // 1. 检查是否已有压缩摘要
    let existing_summary = session.messages.first()
        .and_then(extract_existing_compacted_summary);
    let compacted_prefix_len = usize::from(existing_summary.is_some());
    
    // 2. 分离保留部分和压缩部分
    let keep_from = session.messages.len().saturating_sub(config.preserve_recent_messages);
    let removed = &session.messages[compacted_prefix_len..keep_from];
    let preserved = session.messages[keep_from..].to_vec();
    
    // 3. 生成新摘要
    let summary = merge_compact_summaries(
        existing_summary.as_deref(), 
        &summarize_messages(removed)  // 合并多次压缩
    );
    
    // 4. 构造新的 System 消息
    let continuation = get_compact_continuation_message(&summary, true, !preserved.is_empty());
    
    // 5. 返回压缩后的 session
    CompactedSession {
        messages: [SystemMessage(continuation), ...preserved]
    }
}
```

**摘要生成（`summarize_messages`）：**

```rust
fn summarize_messages(messages: &[ConversationMessage]) -> String {
    // 统计消息类型
    let user_messages = messages.iter().filter(|m| m.role == MessageRole::User).count();
    let assistant_messages = ...;
    let tool_messages = ...;
    
    // 提取工具名列表
    let tool_names: Vec<&str> = messages.iter()
        .flat_map(|m| m.blocks.iter())
        .filter_map(|block| match block {
            ContentBlock::ToolUse { name, .. } => Some(name.as_str()),
            _ => None,
        })
        .collect();
    tool_names.sort_unstable(); tool_names.dedup();
    
    // 提取最近的 user 请求
    let recent_user_requests = collect_recent_role_summaries(messages, MessageRole::User, 3);
    
    // 推断 pending work
    let pending_work = infer_pending_work(messages);
    
    // 收集关键文件路径
    let key_files = collect_key_files(messages);
    
    // 输出带 <summary> tag 的结构化文本
    vec![
        "<summary>".to_string(),
        "Conversation summary:".to_string(),
        format!("- Scope: {} earlier messages compacted (user={}, assistant={}, tool={})",
            messages.len(), user_messages, assistant_messages, tool_messages),
        "- Recent user requests:",
        recent_user_requests...,
        "- Pending work:",
        pending_work...,
        "- Key files referenced: {}.", key_files...,
        "- Key timeline:",
        messages.map(|m| format!("  - {}: {}", role, summarize_block(block))),
        "</summary>".to_string(),
    ].join("\n")
}
```

**多次压缩合并：**

```rust
fn merge_compact_summaries(existing_summary: Option<&str>, new_summary: &str) -> String {
    // 已有摘要：提取 highlights
    let previous_highlights = extract_summary_highlights(existing_summary);
    // 新摘要：提取 highlights + timeline
    let new_highlights = extract_summary_highlights(&new_formatted_summary);
    let new_timeline = extract_summary_timeline(&new_formatted_summary);
    
    // 合并：Previously compacted context + Newly compacted context
    // 保留完整的 timeline（时间线不断累积）
}
```

**文件路径提取（从任意 content 中）：**

```rust
fn collect_key_files(messages: &[ConversationMessage]) -> Vec<String> {
    messages.iter()
        .flat_map(|message| message.blocks.iter())
        .flat_map(|block| match block {
            ContentBlock::Text { text } => text.as_str(),
            ContentBlock::ToolUse { input, .. } => input.as_str(),
            ContentBlock::ToolResult { output, .. } => output.as_str(),
        })
        .flat_map(extract_file_candidates)  // 找包含 / 且有扩展名的 token
        .filter(|candidate| has_interesting_extension(candidate))
        .collect()
}

fn has_interesting_extension(candidate: &str) -> bool {
    Path::new(candidate).extension()
        .is_some_and(|ext| ["rs","ts","tsx","js","json","md"].contains(&ext))
}
```

### 4.3 借鉴价值

| 特性 | 借鉴价值 | OpenClaw 实施建议 |
|------|----------|-------------------|
| Session JSON 自定义序列化 | 高 | 支持会话持久化和恢复 |
| Token 估算 /4 + 1 | 高 | 压缩触发基于估算，不调用 API |
| 多次压缩合并（chaining） | 高 | 每次压缩保留 timeline 累积 |
| 压缩摘要格式 `<summary>` tag | 高 | 结构化摘要便于后续处理 |
| 提取工具名/文件路径/pending work | 高 | 摘要包含语义丰富的元数据 |
| preserved_recent_messages 策略 | 高 | 保留最近 N 条消息用于上下文连贯性 |

---

## 5. 权限系统

### 5.1 权限模式定义

**五级权限（runtime/src/hooks.rs）：**

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum PermissionMode {
    ReadOnly,           // 只读
    WorkspaceWrite,      // 工作区写
    DangerFullAccess,   // 危险全权限
    Prompt,             // 每次提示
    Allow,              // 无条件允许
}

impl PermissionMode {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::ReadOnly => "read-only",
            Self::WorkspaceWrite => "workspace-write",
            Self::DangerFullAccess => "danger-full-access",
            Self::Prompt => "prompt",
            Self::Allow => "allow",
        }
    }
}
```

**权限比较（基于 Ord）：**

```rust
// ReadOnly < WorkspaceWrite < DangerFullAccess < Prompt < Allow
// PermissionMode 实现了 Ord，可以直接比较
```

### 5.2 权限策略

```rust
pub struct PermissionPolicy {
    active_mode: PermissionMode,                    // 当前激活模式
    tool_requirements: BTreeMap<String, PermissionMode>,  // 工具特定要求
}

impl PermissionPolicy {
    pub fn new(active_mode: PermissionMode) -> Self
    pub fn with_tool_requirement(mut self, tool_name: impl Into<String>, required_mode: PermissionMode) -> Self
    
    pub fn required_mode_for(&self, tool_name: &str) -> PermissionMode {
        // 工具特定要求 > 默认 DangerFullAccess
        self.tool_requirements.get(tool_name).copied()
            .unwrap_or(PermissionMode::DangerFullAccess)
    }
    
    pub fn authorize(
        &self,
        tool_name: &str,
        input: &str,
        mut prompter: Option<&mut dyn PermissionPrompter>,
    ) -> PermissionOutcome {
        let current_mode = self.active_mode();
        let required_mode = self.required_mode_for(tool_name);
        
        // 模式足够，直接允许
        if current_mode == PermissionMode::Allow || current_mode >= required_mode {
            return PermissionOutcome::Allow;
        }
        
        // 构建权限请求
        let request = PermissionRequest {
            tool_name: tool_name.to_string(),
            input: input.to_string(),
            current_mode,
            required_mode,
        };
        
        // 需要升级的场景：Prompt 或 WorkspaceWrite->DangerFullAccess
        if current_mode == PermissionMode::Prompt 
            || (current_mode == PermissionMode::WorkspaceWrite 
                && required_mode == PermissionMode::DangerFullAccess) {
            return match prompter.as_mut() {
                Some(prompter) => match prompter.decide(&request) {
                    PermissionPromptDecision::Allow => PermissionOutcome::Allow,
                    PermissionPromptDecision::Deny { reason } => PermissionOutcome::Deny { reason },
                },
                None => PermissionOutcome::Deny { reason: "no prompter".to_string() },
            };
        }
        
        // 权限不足，且不支持 prompt
        PermissionOutcome::Deny { reason: format!(
            "tool '{tool_name}' requires {} permission; current mode is {}",
            required_mode.as_str(), current_mode.as_str()
        )}
    }
}
```

### 5.3 工具权限规格

**内置工具的权限要求（rust/crates/tools/src/lib.rs）：**

```rust
fn mvp_tool_specs() -> Vec<ToolSpec> {
    vec![
        ToolSpec {
            name: "read_file",
            required_permission: PermissionMode::ReadOnly,
            // ...
        },
        ToolSpec {
            name: "write_file",
            required_permission: PermissionMode::WorkspaceWrite,
            // ...
        },
        ToolSpec {
            name: "bash",
            required_permission: PermissionMode::DangerFullAccess,
            // ...
        },
        // ...
    ]
}
```

### 5.4 借鉴价值

| 特性 | 借鉴价值 | OpenClaw 实施建议 |
|------|----------|-------------------|
| 五级权限 + Ord 比较 | 高 | 实现 PermissionMode 枚举，支持 `>=` 比较 |
| 工具特定权限要求 | 高 | 每种工具声明所需权限级别 |
| Prompt 升级模式 | 高 | WorkspaceWrite 下 bash 触发 prompt |
| PermissionPrompter trait | 高 | 抽象化用户交互，支持测试 mock |
| 权限不足的错误消息 | 中 | 清晰的权限错误提示 |

**OpenClaw 具体实现方案：**

```typescript
enum PermissionMode {
  ReadOnly = "read-only",
  WorkspaceWrite = "workspace-write", 
  DangerFullAccess = "danger-full-access",
  Prompt = "prompt",
  Allow = "allow",
}

const toolPermissions: Record<string, PermissionMode> = {
  read: PermissionMode.ReadOnly,
  write: PermissionMode.WorkspaceWrite,
  edit: PermissionMode.WorkspaceWrite,
  exec: PermissionMode.DangerFullAccess,
  browser: PermissionMode.DangerFullAccess,
};

interface PermissionPolicy {
  activeMode: PermissionMode;
  authorize(tool: string, input: string, prompter?: PermissionPrompter): PermissionOutcome;
}

interface PermissionRequest {
  toolName: string;
  input: string;
  currentMode: PermissionMode;
  requiredMode: PermissionMode;
}
```

---

## 6. Git 工作流命令

### 6.1 Commit 命令

```rust
pub fn handle_commit_slash_command(message: &str, cwd: &Path) -> io::Result<String> {
    // 1. 检查是否有变更
    let status = git_stdout(cwd, &["status", "--short"])?;
    if status.trim().is_empty() {
        return Ok("Commit\n  Result           skipped\n  Reason           no workspace changes".to_string());
    }

    // 2. 验证 commit message 非空
    let message = message.trim();
    if message.is_empty() {
        return Err(io::Error::other("generated commit message was empty"));
    }

    // 3. git add -A + git commit --file <temp>
    git_status_ok(cwd, &["add", "-A"])?;
    let path = write_temp_text_file("claw-commit-message", "txt", message)?;
    let path_string = path.to_string_lossy().into_owned();
    git_status_ok(cwd, &["commit", "--file", path_string.as_str()])?;

    Ok(format!("Commit\n  Result           created\n  Message file     {}\n\n{}", path.display(), message))
}
```

### 6.2 Commit-Push-PR 完整流程

```rust
pub fn handle_commit_push_pr_slash_command(
    request: &CommitPushPrRequest,
    cwd: &Path,
) -> io::Result<String> {
    // 1. 检查 gh CLI
    if !command_exists("gh") {
        return Err(io::Error::other("gh CLI is required for /commit-push-pr"));
    }

    // 2. 检测默认分支
    let default_branch = detect_default_branch(cwd)?;
    
    // 3. 如果在默认分支，自动创建新分支
    let mut branch = current_branch(cwd)?;
    let mut created_branch = false;
    if branch == default_branch {
        let hint = if request.branch_name_hint.trim().is_empty() {
            request.pr_title.as_str()
        } else {
            request.branch_name_hint.as_str()
        };
        let next_branch = build_branch_name(hint);
        git_status_ok(cwd, &["switch", "-c", next_branch.as_str()])?;
        branch = next_branch;
        created_branch = true;
    }

    // 4. 如有变更，执行 commit
    let workspace_has_changes = !git_stdout(cwd, &["status", "--short"])?.trim().is_empty();
    let commit_report = if workspace_has_changes {
        let Some(message) = request.commit_message.as_deref() else {
            return Err(io::Error::other("commit message is required when workspace changes are present"));
        };
        Some(handle_commit_slash_command(message, cwd)?)
    } else { None };

    // 5. 检查是否有变更需要推送
    let branch_diff = git_stdout(cwd, &["diff", "--stat", &format!("{default_branch}...HEAD")])?;
    if branch_diff.trim().is_empty() {
        return Ok("Commit/Push/PR\n  Result           skipped\n  Reason           no branch changes to push or open as a pull request".to_string());
    }

    // 6. Push 到 origin
    git_status_ok(cwd, &["push", "--set-upstream", "origin", branch.as_str()])?;

    // 7. 创建 PR
    let body_path = write_temp_text_file("claw-pr-body", "md", request.pr_body.trim())?;
    let create = Command::new("gh")
        .args(["pr", "create", "--title", &request.pr_title, "--body-file", &body_path_string, "--base", &default_branch])
        .current_dir(cwd).output()?;

    // 8. 解析 PR URL（新建或已存在）
    let (result, url) = if create.status.success() {
        ("created", parse_pr_url(&stdout).unwrap_or_else(|| "<unknown>".to_string()))
    } else {
        // PR 可能已存在，尝试查看
        let view = Command::new("gh").args(["pr", "view", "--json", "url"]).current_dir(cwd).output()?;
        ("existing", parse_pr_json_url(&stdout).unwrap_or_else(|| "<unknown>".to_string()))
    };
    
    // 9. 返回结构化报告
    Ok(format!("Commit/Push/PR\n  Result           {result}\n  Branch           {branch}\n  Base             {default_branch}\n  URL              {url}..."))
}
```

### 6.3 辅助函数

```rust
fn detect_default_branch(cwd: &Path) -> io::Result<String> {
    // 优先从 git symbolic-ref 读取
    if let Ok(reference) = git_stdout(cwd, &["symbolic-ref", "refs/remotes/origin/HEAD"]) {
        if let Some(branch) = reference.trim().rsplit('/').next().filter(|v| !v.is_empty()) {
            return Ok(branch.to_string());
        }
    }
    // Fallback: main 或 master
    for branch in ["main", "master"] { ... }
}

fn build_branch_name(hint: &str) -> String {
    // 从 PR title 构建分支名：小写 + 连字符 + 前缀
    let cleaned = hint.chars()
        .map(|c| match c { 'a'..='z'|'0'..='9'|'-' => c, _ => '-' })
        .collect::<String>();
    format!("claw/{}", cleaned.trim_matches('-').chars().take(40).collect::<String>())
}

fn write_temp_text_file(prefix: &str, extension: &str, contents: &str) -> io::Result<PathBuf> {
    let path = std::env::temp_dir()
        .join(format!("{}-{}.{}", prefix, std::process::id(), extension));
    fs::write(&path, contents)?;
    Ok(path)
}
```

### 6.4 借鉴价值

| 特性 | 借鉴价值 | OpenClaw 实施建议 |
|------|----------|-------------------|
| `/commit` 自动检测无变更跳过 | 高 | 实现 slash command 框架 |
| `/commit-push-pr` 一条命令完成 CI/CD | 高 | 封装 gh CLI 调用 |
| 自动分支创建（避免在默认分支 commit） | 高 | 检测当前分支，必要时创建新分支 |
| PR title → branch name 映射 | 中 | 从 commit/PR 标题派生分支名 |
| 结构化输出格式 | 中 | 返回解析好的字段，而非纯文本 |
| 临时文件存储 commit message | 中 | 避免 shell 转义问题 |

---

## 7. 插件系统

### 7.1 Plugin Manifest 格式

**核心结构（plugins/src/lib.rs）：**

```rust
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PluginManifest {
    pub name: String,                    // 插件名称
    pub version: String,                  // 版本号
    pub description: String,              // 描述
    pub permissions: Vec<PluginPermission>,  // 权限列表
    #[serde(rename = "defaultEnabled", default)]
    pub default_enabled: bool,           // 是否默认启用
    #[serde(default)]
    pub hooks: PluginHooks,              // Hook 配置
    #[serde(default)]
    pub lifecycle: PluginLifecycle,      // 生命周期钩子
    #[serde(default)]
    pub tools: Vec<PluginToolManifest>,  // 工具定义
    #[serde(default)]
    pub commands: Vec<PluginCommandManifest>,  // 命令定义
}
```

**示例 plugin.json：**

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "A sample plugin",
  "permissions": ["read", "write"],
  "defaultEnabled": true,
  "hooks": {
    "PreToolUse": ["./hooks/pre.sh"],
    "PostToolUse": ["./hooks/post.sh"]
  },
  "lifecycle": {
    "init": ["./scripts/init.sh"],
    "shutdown": ["./scripts/cleanup.sh"]
  },
  "tools": [{
    "name": "my_tool",
    "description": "Does something",
    "inputSchema": { "type": "object", "properties": { "arg": { "type": "string" } } },
    "command": "python3",
    "args": ["./tools/my_tool.py", "{input}"],
    "requiredPermission": "workspace-write"
  }],
  "commands": [{
    "name": "hello",
    "description": "Says hello",
    "command": "echo hello"
  }]
}
```

### 7.2 工具权限级别

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum PluginToolPermission {
    ReadOnly,
    WorkspaceWrite,
    DangerFullAccess,
}
// 对应 runtime/src/hooks.rs 的 PermissionMode
```

### 7.3 PluginTool 执行

```rust
pub struct PluginTool {
    plugin_id: String,
    plugin_name: String,
    definition: PluginToolDefinition,
    command: String,           // 执行命令
    args: Vec<String>,         // 参数
    required_permission: PluginToolPermission,
    root: Option<PathBuf>,    // 插件根目录（用于相对路径解析）
}

impl PluginTool {
    pub fn execute(&self, input: &Value) -> Result<String, PluginError> {
        // 1. 构造命令行参数（替换 {input} 占位符）
        let args = self.args.iter()
            .map(|arg| arg.replace("{input}", &input.to_string()))
            .collect::<Vec<_>>();
        
        // 2. 设置环境变量
        let mut cmd = Command::new(&self.command);
        cmd.args(&args);
        cmd.env("CLAW_PLUGIN_ID", &self.plugin_id);
        cmd.env("CLAW_TOOL_NAME", &self.definition.name);
        cmd.env("CLAW_TOOL_INPUT", input.to_string());
        
        // 3. 如有 root，命令基于 root 相对路径
        if let Some(root) = &self.root {
            cmd.current_dir(root);
        }
        
        // 4. 执行并捕获输出
        let output = cmd.output()?;
        if output.status.success() {
            Ok(String::from_utf8_lossy(&output.stdout).into_owned())
        } else {
            Err(PluginError::ExecutionFailure(
                String::from_utf8_lossy(&output.stderr).into_owned()
            ))
        }
    }
}
```

### 7.4 PluginRegistry 生命周期

```rust
impl PluginRegistry {
    pub fn aggregated_tools(&self) -> Result<Vec<PluginTool>, PluginError> {
        let mut tools = Vec::new();
        let mut seen_names = BTreeMap::new();  // 检测工具名冲突
        for plugin in self.plugins.iter().filter(|plugin| plugin.is_enabled()) {
            for tool in plugin.tools() {
                if let Some(existing) = seen_names.insert(tool.definition().name.clone(), tool.plugin_id().to_string()) {
                    return Err(PluginError::InvalidManifest(format!(
                        "tool `{}` is defined by both `{}` and `{}`",
                        tool.definition().name, existing, tool.plugin_id()
                    )));
                }
                tools.push(tool.clone());
            }
        }
        Ok(tools)
    }
    
    pub fn initialize(&self) -> Result<(), PluginError> {
        // 按顺序初始化所有启用的插件
        for plugin in self.plugins.iter().filter(|plugin| plugin.is_enabled()) {
            plugin.initialize()?;  // 执行 lifecycle.init 命令
        }
        Ok(())
    }
    
    pub fn shutdown(&self) -> Result<(), PluginError> {
        // 逆序 shutdown
        for plugin in self.plugins.iter().rev().filter(|plugin| plugin.is_enabled()) {
            plugin.shutdown()?;  // 执行 lifecycle.shutdown 命令
        }
        Ok(())
    }
}
```

### 7.5 PluginManager 配置

```rust
pub struct PluginManagerConfig {
    pub config_home: PathBuf,           // 配置目录 ~/.claw/plugins/
    pub enabled_plugins: BTreeMap<String, bool>,  // plugin_id -> enabled
    pub external_dirs: Vec<PathBuf>,    // 外部插件目录
    pub install_root: Option<PathBuf>,  // 安装根目录
    pub registry_path: Option<PathBuf>, // registry 文件路径
    pub bundled_root: Option<PathBuf>,  // 捆绑插件目录
}
```

### 7.6 借鉴价值

| 特性 | 借鉴价值 | OpenClaw 实施建议 |
|------|----------|-------------------|
| plugin.json manifest 格式 | 高 | 定义插件描述格式（JSON Schema） |
| 生命周期 Init/Shutdown | 高 | 插件安装/卸载时执行脚本 |
| 工具注册 + 冲突检测 | 高 | registry 防止同名工具覆盖 |
| `{input}` 占位符参数替换 | 高 | 工具调用时注入输入 JSON |
| 工具名冲突报错 | 高 | 多个插件不能定义同名工具 |
| aggregated_hooks 合并 | 中 | 多插件 hooks 链式执行 |
| 逆序 shutdown | 中 | 后进先出，依赖关系逆序清理 |

---

## 8. 优先级清单

### 🔴 高优先级（可直接借鉴，实现价值高）

| # | 特性 | 来源模块 | 借鉴方式 | OpenClaw 实施难度 |
|---|------|----------|----------|-------------------|
| 1 | **Hook 系统**（PreToolUse/PostToolUse，退出码语义） | runtime/src/hooks.rs | 在工具执行层插入 hook 拦截点，支持外部命令验证/修改/拒绝 | 中（需要工具执行流水线改造） |
| 2 | **五级权限模式 + 工具特定要求** | runtime/src/hooks.rs (PermissionMode) | 为每种工具声明权限级别，实现 `authorize()` 检查 | 低（枚举 + BTreeMap 配置） |
| 3 | **Session 压缩**（token 估算 + 摘要链式合并） | runtime/src/compact.rs | 当会话超过 token 上限时，自动压缩历史消息 | 中（需要会话状态管理改造） |
| 4 | **工具别名映射**（read→read_file） | tools/src/lib.rs (normalize_allowed_tools) | 用户可用短名，registry 自动展开 | 低（字符串替换） |
| 5 | **Bash 超时处理**（async timeout + interrupted flag） | runtime/src/bash.rs | exec 工具支持 `timeout` 参数，超时返回特殊标记 | 低（tokio timeout 封装） |
| 6 | **Bash 后台任务**（background_task_id） | runtime/src/bash.rs | 支持 `run_in_background: true`，返回进程 ID | 低（spawn + 返回 PID） |
| 7 | **路径规范化**（normalize_path） | runtime/src/file_ops.rs | read/write/edit 使用 canonicalize 防止 path traversal | 低（PathBuf 操作） |
| 8 | **MCP 工具名规范化** | runtime/src/mcp.rs | MCP server 工具名转 `mcp__server__tool` 格式 | 低（字符串处理） |
| 9 | **Commit-Push-PR 流程** | commands/src/lib.rs | 实现 `/commit-push-pr` slash command | 中（需要 slash command 框架） |
| 10 | **Plugin manifest + 生命周期** | plugins/src/lib.rs | 插件 install/remove/init/shutdown hooks | 高（需要插件架构设计） |
| 11 | **大输出持久化**（persisted_output_path） | runtime/src/bash.rs | exec 输出超限时写入 tmp 文件而非内存 | 低（fs::write 条件判断） |
| 12 | **Structured patch**（文件修改的 diff 生成） | runtime/src/file_ops.rs | write/edit 返回 unified diff 结构 | 低（简单字符串处理） |

### 🟡 中优先级（有借鉴价值，需要一定工作量）

| # | 特性 | 来源模块 | 借鉴方式 | OpenClaw 实施难度 |
|---|------|----------|----------|-------------------|
| 13 | **PermissionPrompter trait**（可测试 mock） | runtime/src/hooks.rs | 抽象用户 prompt 交互，支持单元测试 | 低（trait 定义） |
| 14 | **MCP server 配置签名 + hash** | runtime/src/mcp.rs | 检测配置变化触发 server 重启 | 低（字符串 hash） |
| 15 | **GrepSearch 多模式**（content/count/files） | runtime/src/file_ops.rs | grep 工具增加 output_mode 参数 | 低（enum 分支） |
| 16 | **read_file offset/limit** | runtime/src/file_ops.rs | read 工具支持行范围参数 | 低（ slice 行数组） |
| 17 | **glob_search 排序**（按修改时间） | runtime/src/file_ops.rs | glob 结果按 mtime 降序，返回 top 100 | 低（sort_by_key） |
| 18 | **自动分支创建**（避免在默认分支 commit） | commands/src/lib.rs | commit 时检测当前分支 | 低（git 命令封装） |
| 19 | **Plugin 工具冲突检测** | plugins/src/lib.rs | 多插件不能定义同名工具 | 低（BTreeMap 检查） |
| 20 | **聚合 hooks 合并** | plugins/src/lib.rs (aggregated_hooks) | 多插件 PreToolUse hooks 顺序执行 | 中（plugin 架构） |
| 21 | **Edit replace_all** | runtime/src/file_ops.rs | edit 工具支持 replace_all 参数 | 低（Rust `replace` vs `replacen`） |
| 22 | **infer_pending_work**（从消息推断 TODO） | runtime/src/compact.rs | 压缩摘要中提取 "next"/"todo"/"pending" 内容 | 低（字符串搜索） |
| 23 | **extract_key_files**（从 content 提取文件路径） | runtime/src/compact.rs | 压缩摘要中包含关键文件列表 | 低（regex 提取） |

### 🟢 低优先级（有趣但实施收益有限）

| # | 特性 | 来源模块 | 备注 |
|---|------|----------|------|
| 24 | **CCR Proxy URL 解包** | runtime/src/mcp.rs | Anthropic 特定场景 |
| 25 | **stable_hex_hash**（FNV hash） | runtime/src/mcp.rs | 配置签名用，简单高效 |
| 26 | **collapse_underscores** | runtime/src/mcp.rs | 清理连续下划线 |
| 27 | **write_temp_text_file**（带 PID） | commands/src/lib.rs | 避免并发冲突 |
| 28 | **parse_pr_url / parse_pr_json_url** | commands/src/lib.rs | gh CLI 输出解析 |

---

## 附录：核心文件索引

| 文件 | 行数 | 核心内容 |
|------|------|----------|
| `runtime/src/hooks.rs` | 357 | HookRunner + PermissionMode/PermissionPolicy |
| `runtime/src/permissions.rs` | ~200（同 hooks.rs） | 权限类型定义（同文件） |
| `runtime/src/mcp.rs` | 300 | MCP 命名规范 + 签名 |
| `runtime/src/mcp_client.rs` | ~300 | MCP Transport 类型 |
| `runtime/src/compact.rs` | 702 | 压缩算法完整实现 |
| `runtime/src/session.rs` | 436 | Session 数据模型 |
| `runtime/src/conversation.rs` | ~800 | ConversationRuntime + 工具执行循环 |
| `runtime/src/bash.rs` | ~250 | Bash 命令执行 |
| `runtime/src/file_ops.rs` | ~500 | read/write/edit/grep/glob |
| `tools/src/lib.rs` | 4469 | 工具注册表 + 所有工具入口 |
| `commands/src/lib.rs` | 2511 | Git 命令（commit/branch/worktree/PR） |
| `plugins/src/lib.rs` | 2943 | 插件系统完整实现 |
| `plugins/src/hooks.rs` | 395 | 插件 HookRunner |

---

*报告生成完毕*
