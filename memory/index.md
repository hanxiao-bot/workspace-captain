# Memory Index

> Captain 的记忆索引 — 快速定位知识所在

---

## Long-term
- [MEMORY.md](../MEMORY.md) — 核心长期记忆（铁律、人物、项目、教训）

## Daily
- [2026-03-28](2026-03-28.md) — 日志清理脚本
- [2026-03-29](2026-03-29.md)
- [2026-03-31](2026-03-31.md)
- [2026-04-01](2026-04-01.md) — 系统维护、股票系统全面修复、Skills配置
- [2026-04-02](2026-04-02.md) — OpenClaw增强、claw-code研究

## Sources（记忆来源）
> 从各系统同步的原始数据
- [claude-code/](sources/claude-code/) — Claude Code交互记录
  - [2026-03-21](sources/claude-code/2026-03-21.jsonl)
- [self-improving/](sources/self-improving/) — Self-improving agent记忆
  - [memory](sources/self-improving/memory.md)
  - [reflections](sources/self-improving/reflections.md)
  - [corrections](sources/self-improving/corrections.md)
- [mine/](sources/mine/) — Captain自身产生的记忆（预留）

## Patterns（提炼的模式）
> 从Sources中提炼的结构化知识
- [error-patterns](patterns/error-patterns.md) — 错误模式与避坑指南
- [workflow-patterns](patterns/workflow-patterns.md) — Captain工作流模式
- [user-preferences](patterns/user-preferences.md) — Shawn行为偏好

## Knowledge（领域知识）
- [stock-system](domain/stock-system.md) — 股票分析系统（项目详情、验证状态、API字段规范）
- [openclaw](domain/openclaw.md) — OpenClaw配置、铁律、调度规则

## Tools（工具配置）
- [skills](tools/skills.md) — Skills状态一览（clawsec、github、deep-debugging等）
- [git-workflow](tools/git-workflow.md) — Git工作流配置
- [hook-system](tools/hook-system.md) — Hook系统配置

---

## 记忆维护规则
1. 重大决策/教训 → MEMORY.md
2. 每日工作记录 → memory/YYYY-MM-DD.md
3. 领域知识沉淀 → memory/domain/*.md
4. 工具配置变更 → memory/tools/*.md
5. Sources数据定期同步（Claude Code / Self-improving）
6. 从Sources提炼模式 → memory/patterns/*.md
7. 定期更新本索引

---

_Last updated: 2026-04-03_
