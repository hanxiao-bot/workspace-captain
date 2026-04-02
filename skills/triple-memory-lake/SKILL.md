---
name: triple-memory-lake
version: 1.0.0
description: Triple memory system integration - unifies OpenClaw, Claude Code, and self-improving agent memories into a single knowledge lake
---

# Triple Memory Lake

# Triple Memory Lake

基于三个记忆系统整合的统一知识湖。

## 核心功能

### 1. 三源数据同步
- Claude Code JSONL → memory/sources/claude-code/
- self-improving metrics → memory/sources/self-improving/
- OpenClaw daily logs → memory/sources/mine/

### 2. 模式提炼
- 错误模式汇总
- 工作流模式
- 用户偏好

### 3. 知识沉淀
- 长期记忆
- 领域知识
- 工具知识

## 目录结构

```
memory/
├── sources/          # 原始数据
│   ├── claude-code/  # Claude Code JSONL 日志
│   ├── self-improving/ # self-improving 指标
│   └── mine/         # OpenClaw 每日日志
├── patterns/         # 提炼模式
│   ├── errors/       # 错误模式汇总
│   ├── workflows/    # 工作流模式
│   └── preferences/  # 用户偏好
├── knowledge/        # 知识沉淀
│   ├── long-term/    # 长期记忆
│   ├── domain/       # 领域知识
│   └── tools/        # 工具知识
└── index.md          # 统一入口
```

## 使用方式

### 同步所有数据源
```bash
python3 scripts/sync-all.py
```

### 单独同步某个数据源
```bash
python3 scripts/sync-claude-code.py
python3 scripts/sync-self-improving.py
```

### 提炼模式
```bash
python3 scripts/pattern-miner.py
```

### 查看知识湖状态
```bash
cat memory/index.md
```

## 同步策略

- **增量同步**：只处理新增文件，避免重复
- **时间戳记录**：记录最后同步时间
- **去重机制**：基于内容hash去重
- **模式发现**：自动从原始数据中发现新模式

## 数据源说明

### Claude Code
- 路径：`~/.claude/projects/*/sessions/*.jsonl`
- 内容：对话历史、工具调用、错误信息

### Self-Improving
- 路径：`~/.openclaw/agents/*/metrics.json`
- 内容：性能指标、成功率、响应时间

### OpenClaw Daily Logs
- 路径：`~/.openclaw/workspace-captain/memory/*.md`
- 内容：每日工作记录、决策、上下文
