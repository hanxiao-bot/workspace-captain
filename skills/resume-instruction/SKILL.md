---
name: resume-instruction
description: Resume Instruction - Auto inject continue-directly instruction after compaction
---

# Resume Instruction - Post-Compaction Directive

## Overview

After session compaction, automatically inject a directive to prevent the model from recapping or re-summarizing.

## The Problem

After compaction, models often waste tokens saying things like:
- "As I mentioned earlier..."
- "Building on the summary..."
- "Let me recap what we discussed..."

## The Solution

Inject this instruction after compaction:

```markdown
Continue directly — do not acknowledge the summary, do not recap what was happening, and do not preface with continuation text.
```

## Implementation

This is implemented via `after_compaction` hook:

```javascript
api.registerHook("after_compaction", async ({ event, ctx }) => {
  const instruction = `\n\n## Resume Directive
Continue directly from where the conversation left off. Do not summarize, recapi, or acknowledge the previous summary.`;

  return {
    extraSystemPrompt: instruction
  };
});
```

## Alternative: AGENTS.md Integration

Add to AGENTS.md Session Startup section:

```markdown
## Session Startup
After compaction, read the summary and continue immediately without acknowledgment.

## Resume Directive
Continue the conversation from where it left off.
- Do NOT say "As I mentioned earlier"
- Do NOT say "Building on the summary"
- Do NOT say "Let me recap"
- Do NOT preface with "Continuing..."
```

## Configuration

```json5
{
  "agents": {
    "defaults": {
      "compaction": {
        "resumeDirective": true
      }
    }
  }
}
```

## Effect

Before:
```
"As I mentioned in the summary, you wanted to..."
"We discussed X and now..."
"Building on the previous points..."
```

After:
```
Direct continuation with no preamble.
```
