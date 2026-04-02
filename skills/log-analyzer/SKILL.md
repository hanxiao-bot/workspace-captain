# Log Analyzer - Log Analysis

## Overview

OpenClaw has a built-in diagnostic system for tracing execution paths via `diagnostic-events`.

## Enable Diagnostics

```bash
# Enable via environment variable
OPENCLAW_DIAGNOSTICS=agent.embedded,gateway.*

# Or in config
{
  "diagnostics": {
    "enabled": true,
    "flags": ["agent.embedded", "model-fallback", "retry-policy"]
  }
}
```

## Log Location

Diagnostic logs output to:
```
/tmp/openclaw/openclaw-YYYY-MM-DD.log
```

JSONL format:
```json
{"subsystem":"agent.embedded","level":"info","message":"tool call: exec","ts":1743556800000,"seq":123}
```

## Subsystem Log Levels

| Subsystem | Description |
|-----------|-------------|
| agent.embedded | Agent execution flow |
| model-fallback | Model switch retry |
| retry-policy | Retry policy |
| errors | Error classification |
| gateway | Gateway events |

## Analysis Commands

```bash
# Find errors
grep '"level":"error"' /tmp/openclaw/openclaw-2026-04-01.log

# Trace specific session
grep "sessionKey.*main:feishu" /tmp/openclaw/openclaw-2026-04-01.log | jq .

# Count tool calls
grep "tool_call" /tmp/openclaw/openclaw-2026-04-01.log | jq -r .message | sort | uniq -c

# View retries
grep "retry" /tmp/openclaw/openclaw-2026-04-01.log | jq .
```

## Common Error Codes

| Error | Description | Action |
|-------|-------------|--------|
| 429 | Rate limit | Wait and retry |
| 402 | Billing error | Check API quota |
| 503 | Service overloaded | Wait and retry |
| context_overflow | Context overflow | Triggers compaction |

## Debugging Flow

1. Enable diagnostics: `OPENCLAW_DIAGNOSTICS=*`
2. Reproduce the issue
3. View logs: `tail -f /tmp/openclaw/openclaw-$(date +%Y-%m-%d).log`
4. Filter relevant subsystems
5. Analyze call chain
