# Token Cost - Token Cost Analysis

## Overview

OpenClaw automatically tracks token usage and cost via session transcript JSONL.

## Data Source

Session transcript files:
```
~/.openclaw/sessions/{agentId}/{sessionId}.jsonl
```

Each message contains an `usage` field:
```json
{
  "type": "message",
  "role": "assistant",
  "usage": {
    "input_tokens": 1200,
    "output_tokens": 450,
    "cache_read_input_tokens": 8000,
    "cache_write_input_tokens": 2000
  }
}
```

## Cost Calculation

### Model Pricing (Reference)

| Model | Input ($/1M) | Output ($/1M) | Cache Read |
|-------|-------------|--------------|-----------|
| claude-sonnet-4 | $3 | $15 | $0.30 |
| gpt-4o | $5 | $15 | - |
| minimax-m2 | $0 | $0.01 | - |

### Calculation Formula

```
Total cost = input_cost + output_cost + cache_read_cost

input_cost = input_tokens / 1M * input_price
output_cost = output_tokens / 1M * output_price
cache_read_cost = cache_read_tokens / 1M * cache_read_price
```

## Tracking Methods

### 1. OpenClaw Built-in Stats

View session stats:
```
Agent → Settings → Session → Cost
```

### 2. Manual JSONL Analysis

```bash
# Extract all usage
cat session.jsonl | jq -r 'select(.usage) | .usage'

# Calculate total tokens
cat session.jsonl | jq -r 'select(.usage) | .usage.input_tokens' | awk '{s+=$1} END {print "Input: " s}'
cat session.jsonl | jq -r 'select(.usage) | .usage.output_tokens' | awk '{s+=$1} END {print "Output: " s}'
```

### 3. Cost Script

```python
#!/usr/bin/env python3
import json
import sys

def estimate_cost(usage, model="minimax-m2"):
    prices = {
        "minimax-m2": {"input": 0, "output": 0.01, "cache_read": 0},
        "claude-sonnet-4": {"input": 3, "output": 15, "cache_read": 0.30},
        "gpt-4o": {"input": 5, "output": 15, "cache_read": 0}
    }
    p = prices.get(model, prices["minimax-m2"])
    return (
        usage.get("input_tokens", 0) / 1e6 * p["input"] +
        usage.get("output_tokens", 0) / 1e6 * p["output"] +
        usage.get("cache_read_input_tokens", 0) / 1e6 * p["cache_read"]
    )

total = 0
for line in sys.stdin:
    entry = json.loads(line)
    if entry.get("usage"):
        cost = estimate_cost(entry["usage"])
        total += cost

print(f"Total estimated cost: ${total:.4f}")
```

## Optimization Strategies

### 1. Enable Compression

```json5
{
  "agents": {
    "defaults": {
      "compaction": {
        "mode": "auto",
        "threshold": "75%"
      }
    }
  }
}
```

### 2. Use Caching

- Keep sessions alive (reuse cache_write)
- Avoid frequently creating new sessions

### 3. Choose Appropriate Model

| Task | Recommended Model | Reason |
|------|-------------------|--------|
| Simple Q&A | minimax-m2 | Free/cheap |
| Document summary | minimax-m2.5 | Long context |
| Complex reasoning | claude-sonnet-4 | Better quality |
