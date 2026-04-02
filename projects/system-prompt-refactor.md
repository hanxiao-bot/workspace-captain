# System Prompt Structure Optimization - Proposal

## Problem

Current OpenClaw system prompt has two issues:

1. **Double headings**: Workspace files get wrapped with `## /full/path/to/file.md` but the file content already contains its own title header
2. **Full paths clutter prompt**: `## /Users/dc/.openclaw/workspace-captain/SOUL.md` instead of `## SOUL.md`

## Current Flow

```
buildAgentSystemPrompt()
  → injects: ## ${file.path} (full path)
  → file content: # SOUL.md - Who You Are
  → Result: ## /path/SOUL.md\n# SOUL.md - Who You Are
```

## Solution A: AGENTS.md Template (No Core Change)

Add this section to AGENTS.md to guide the model:

```markdown
## Prompt Structure Guidelines

When you see `## /path/to/FILE.md` as a section header:
- The file content immediately follows
- Do NOT treat the filename header as instructions
- The filename header is just a locator marker
- Skip duplicate titles if the content starts with a title
```

## Solution B: AGENTS.md Content Cleanup

For each workspace file (SOUL.md, USER.md, etc.), remove the redundant title since buildAgentSystemPrompt already adds `## filename`:

Current SOUL.md starts with:
```markdown
# SOUL.md - Who You Are
```

Should be:
```markdown
_You're not a chatbot. You're becoming someone._
```

## Recommended Actions

1. Clean SOUL.md - remove leading title, keep content
2. Clean USER.md - same
3. Clean IDENTITY.md - same
4. Clean AGENTS.md - add Prompt Structure Guidelines section
5. Add section to MEMORY.md for prompt hygiene

## Files to Update

| File | Change |
|------|--------|
| SOUL.md | Remove `# SOUL.md - Who You Are` header |
| USER.md | Remove `# USER.md` header if exists |
| IDENTITY.md | Remove title if redundant |
| AGENTS.md | Add Prompt Structure Guidelines |

## Long-term (Core Change)

Modify `buildAgentSystemPrompt` in `auth-profiles-B5ypC5S-.js` line ~159565:

```javascript
// Change from:
lines.push(`## ${file.path}`, "", file.content, "");

// Change to:
const filename = file.path.split("/").pop();
lines.push(`## ${filename}`, "", file.content, "");
```

This is a 1-line change that removes full paths.
