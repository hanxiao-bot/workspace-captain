# Workflow Patterns

> Captain工作流模式 — 调度、验收、交付

---

## Captain调度模式
1. 收到需求 → 拆解任务
2. 分给Developer写代码/脚本
3. 完工后交给Secretary整理文档
4. 最后汇总给用户
5. **不自己写代码、不自己写文档，只负责调度与验收**

## 验证优先
- "要验证可用性"是口头禅
- 命令结果必须实际运行验证
- 不接受"应该可以"的说法

## 模型选择规则（2026-03-28锁定）
| 任务类型 | 模型 | 来源 |
|----------|------|------|
| 代码任务 | `ollama/deepseek-r1:70b` | 本地 |
| 文档/轻量 | `ollama/qwen3:14b` | 本地 |
| 复杂推理 | `ollama/qwq:32b` | 本地 |
| 默认云端 | `minimax-portal/MiniMax-M2.7` | volcengine |

## Ollama路由铁律
- 🚫 `qwen3:32b` — M3 Ultra Metal性能极差
- 🚫 任何云端fallback到 deepseek-chat/minimax/volcengine

## 子Agent调度格式
```
sessions_spawn时指定 model: "ollama/deepseek-r1:70b"
```

---

_Last updated: 2026-04-03_
