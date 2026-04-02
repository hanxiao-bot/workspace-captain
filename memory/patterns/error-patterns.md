# Error Patterns

> 从实际错误中提炼的模式 — 避免重复踩坑

---

## 模型调度错误
- **qwen3:32b on M3 Ultra** — Metal性能极差，禁止使用
- **云端fallback** — 禁止 deepseek-chat/minimax/volcengine fallback
- **默认模型** — 使用 minimax-portal/MiniMax-M2.7

## 子Agent工具约束
- exec/浏览器类工具需谨慎，避免危险命令
- write/edit受workspace path boundary限制
- gateway/cron/nodes默认禁止给子Agent使用

## Shell安全
- 危险字符过滤：`;&|\`$`<>` `'` `"` `\r` `\n`
- 禁止flag注入（`-`开头参数需白名单）
- elevated权限需要明确allowFrom配置

## Path Boundary逃逸
- `../` 逃逸被 lexical + canonical 双重检查阻止
- symlink逃逸被检测并阻止
- 所有文件操作受workspace边界限制

## 记忆系统问题
- Claude Code数据只有2026-03-21一次同步
- self-improving数据需定期同步
- patterns/目录为新增，需持续充实

---

_Last updated: 2026-04-03_
