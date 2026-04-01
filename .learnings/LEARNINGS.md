# Learnings

Corrections, insights, and knowledge gaps captured during development.

**Categories**: correction | insight | knowledge_gap | best_practice
**Areas**: frontend | backend | infra | tests | docs | config
**Statuses**: pending | in_progress | resolved | wont_fix | promoted | promoted_to_skill

## Status Definitions

| Status | Meaning |
|--------|---------|
| `pending` | Not yet addressed |
| `in_progress` | Actively being worked on |
| `resolved` | Issue fixed or knowledge integrated |
| `wont_fix` | Decided not to address (reason in Resolution) |
| `promoted` | Elevated to CLAUDE.md, AGENTS.md, or copilot-instructions.md |
| `promoted_to_skill` | Extracted as a reusable skill |

## Skill Extraction Fields

When a learning is promoted to a skill, add these fields:

```markdown
**Status**: promoted_to_skill
**Skill-Path**: skills/skill-name
```

Example:
```markdown
## [LRN-20250115-001] best_practice

**Logged**: 2025-01-15T10:00:00Z
**Priority**: high
**Status**: promoted_to_skill
**Skill-Path**: skills/docker-m1-fixes
**Area**: infra

### Summary
Docker build fails on Apple Silicon due to platform mismatch
...
```

---


## [LRN-20260328-001] best_practice

**Logged**: 2026-03-28T02:30:00Z
**Priority**: high
**Status**: promoted
**Promoted**: MEMORY.md, AGENTS.md
**Area**: infra

### Summary
子Agent任务完成后必须验证，不能盲目信任其结果

### Details
多个项目中，Developer subagent 报告"已完成"但实际未生效或报错被吞。需要独立验证。
案例：数据库写入链路，subagent 报告成功，但 stocks.db 是 0 字节。

### Suggested Action
- subagent 完成后立即 exec 验证关键输出
- 不要在验证完成前告诉用户"已完成"
- cron 等基础设施任务，必须实际运行验证

### Metadata
- Source: error
- Tags: subagent, verification, trust-but-verify
- Recurrence-Count: 3
- First-Seen: 2026-03-19
- Last-Seen: 2026-03-28

---
