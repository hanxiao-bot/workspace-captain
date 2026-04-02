---
name: memory-expiry
description: Memory Expiry - Policy for automatic memory cleanup
---

# Memory Expiry - Memory Cleanup Policy

## Overview

Manage memory lifecycle: when to delete old daily memory files, what to keep in MEMORY.md, and how to prevent memory bloat.

## Memory Layers

| Layer | Location | Lifetime | Auto-cleanup? |
|-------|----------|---------|----------------|
| Long-term | MEMORY.md | Forever | No |
| Daily | memory/YYYY-MM-DD.md | 30 days | Yes (configurable) |
| Session | Transcript | Session only | Auto |

## Expiry Rules

### Daily Memory (memory/*.md)
- Default retention: **30 days**
- Keep if: contains unresolved TODOs
- Keep if: contains key decisions
- Delete if: older than 30 days with no TODO flag

### MEMORY.md
- Never auto-delete
- Review monthly: remove outdated info
- Update after major sessions

## Implementation

### Cleanup Script

```bash
#!/bin/bash
# memory-expiry.sh
DAYS=30
MEMORY_DIR="memory"

find "$MEMORY_DIR" -name "*.md" -mtime +$DAYS | while read f; do
  # Skip if contains TODO
  if ! grep -q "TODO\|待办\|未完成" "$f"; then
    echo "Expiring: $f"
    rm "$f"
  fi
done
```

### Cron Job

```json5
{
  "cron": {
    "memoryExpiry": {
      "enabled": true,
      "schedule": "0 3 * * *",  // 3 AM daily
      "retentionDays": 30,
      "keepTodos": true
    }
  }
}
```

## Memory Review Checklist

Monthly review of MEMORY.md:

- [ ] Remove outdated project references
- [ ] Archive old decisions that are no longer relevant
- [ ] Update team/preference notes if changed
- [ ] Consolidate daily memories into permanent notes
- [ ] Check for contradictions with current state

## Signs of Memory Bloat

- MEMORY.md > 100KB
- memory/ contains > 60 files
- Search results include irrelevant old sessions
- Token usage increasing without conversation growth

## Prevention

1. Write concisely in daily memory
2. Use date-based filenames for easy deletion
3. Flag important entries with `TODO` or `KEY`
4. Review MEMORY.md monthly
