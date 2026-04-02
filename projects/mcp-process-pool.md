# MCP Process Pool - Feature Proposal

## Problem

Every MCP tool call spawns a new OS process. This adds ~200-500ms overhead per call with no process reuse.

## Current Architecture

```
Tool Call → spawn() → init → JSON-RPC → exit
Tool Call → spawn() → init → JSON-RPC → exit
Tool Call → spawn() → init → JSON-RPC → exit
```

## Proposed Architecture

```
Pool → acquire() → reuse existing process
     → release() → return to pool (idle)
     → idle timeout → terminate
```

## Implementation

### Config Schema

```json5
{
  "mcp": {
    "servers": {
      "github": {
        "command": "uvx",
        "args": ["mcp-server-github"],
        "pool": {
          "enabled": true,
          "size": 1,
          "idleTimeoutMs": 60000,
          "maxRequests": 500
        }
      }
    }
  }
}
```

### Pool Semantics

| Parameter | Default | Description |
|-----------|---------|-------------|
| size | 1 | Processes per server |
| idleTimeoutMs | 60000 | Terminate after idle |
| maxRequests | 500 | Recycle after N requests |
| enabled | false | Opt-in |

## Benefits

- Warm calls: ~0ms overhead (vs 200-500ms cold)
- Lower CPU/memory
- Process isolation per server

## Effort

- Core changes required
- Estimated: 2-4 weeks
- Files: new pool class, config schema, QMDManager integration

## Status

**Feature Request** - requires OpenClaw core team
