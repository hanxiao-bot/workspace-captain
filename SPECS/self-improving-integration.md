# 自我提升体系整合规范
> 版本：v1.0.0 | 日期：2026-03-28 | 状态：已整合

---

## 整合架构

```
~/self-improving/               ← 三技能统一入口
├── memory.md                   ← HOT记忆（常驻）
├── corrections.md              ← 纠正日志（最近50条）
├── index.md                    ← 存储索引
├── projects/                  ← 按项目分类
├── domains/                   ← 按领域分类
└── archive/                   ← 归档（30天未用）

~/proactivity/                 ← 主动性增强
├── memory.md                   ← 主动性规则
├── session-state.md            ← 当前会话状态
├── heartbeat.md               ← 定期检查清单
├── patterns.md                ← 成功案例
└── log.md                     ← 主动行为日志

~/.openclaw/hooks/self-improvement/  ← 自动错误捕获
├── HOOK.md
└── ...

~/.openclaw/workspace-captain/.learnings/  ← 开发专项
├── LEARNINGS.md               ← 开发教训
├── ERRORS.md                  ← 错误记录
└── FEATURE_REQUESTS.md        ← 需求池
```

## 三技能来源

| 原技能 | 取用内容 | 整合后位置 |
|--------|---------|-----------|
| `self-improving` (ivangdavila) | HOT/WARM/COLD 框架 | `~/self-improving/` |
| `self-improving-agent` (pskoett) | Hook + ERR/LRN 分类 | `~/.openclaw/hooks/` + `.learnings/` |
| `self-improving-proactive-agent` | 主动性 + session-state | `~/proactivity/` |

## 晋升路径

```
用户纠正 or 发现错误
    ↓
corrections.md（≤50条）
    ↓
3x重复 → memory.md（HOT，≤100行）
    ↓
30天未用 → projects/（WARM）
    ↓
90天未用 → archive/（COLD）
```

## 触发规则

| 触发 | 记录位置 |
|------|---------|
| 用户纠正我 | `corrections.md` |
| 命令失败 | `ERRORS.md` |
| 子Agent验证通过 | `LEARNINGS.md` |
| 主动发现更好方法 | `LEARNINGS.md` |
| 用户要的不存在 | `FEATURE_REQUESTS.md` |
| 任务多步骤 | `session-state.md` |

## 命名规范

- corrections: `[LRN-YYYYMMDD-NNN]` 格式
- errors: `[ERR-YYYYMMDD-NNN]` 格式
- learnings: `[LRN-YYYYMMDD-NNN]` 格式
- feature requests: `[FEAT-YYYYMMDD-NNN]` 格式

## 规则

1. **不推断沉默**：用户没说话就不行动
2. **3x才晋升**：单独出现不晋升，等3次重复
3. **删除前先归档**：不删文件，降级到 archive
4. **每次会话读 memory.md**：快速恢复上下文
5. **心跳时检查 corrections.md**：看是否有3x重复模式
