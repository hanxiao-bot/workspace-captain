---
name: prompt-inject
description: Prompt Dynamic Injection - Inject context before prompt is built
---

# Prompt Inject - Dynamic Prompt Injection

## Overview

Use `before_prompt_build` hook to inject dynamic context into the system prompt.

## Use Cases

- Inject current project tech stack
- Add team coding standards
- Inject today's date/reminders
- Add user-specific context

## Implementation

```javascript
api.registerHook("before_prompt_build", async ({ event, ctx }) => {
  const injections = [];
  
  // Inject project context
  const projectContext = await getProjectContext();
  if (projectContext) {
    injections.push(`## Project Context\n${projectContext}`);
  }
  
  // Inject team standards
  injections.push(`## Team Standards\n${await getTeamStandards()}`);
  
  // Inject reminders
  const reminders = await getReminders();
  if (reminders.length > 0) {
    injections.push(`## Reminders\n${reminders.join("\n")}`);
  }
  
  return {
    prompt: injections.join("\n\n")
  };
});
```

## Configuration

The hook reads from config:

```json5
{
  "agents": {
    "defaults": {
      "promptInject": {
        "projectContext": true,
        "teamStandards": true,
        "reminders": true,
        "customSections": []
      }
    }
  }
}
```

## Example: Tech Stack Detection

```javascript
api.registerHook("before_prompt_build", async ({ event, ctx }) => {
  // Detect project type from workspace
  const files = await listWorkspaceFiles();
  const techStack = detectTechStack(files);
  
  return {
    prompt: `## Tech Stack\nThis project uses: ${techStack.join(", ")}`
  };
});
```

## Best Practices

- Keep injections small (< 500 chars)
- Don't override core instructions
- Use for context only, not commands
- Check config to enable/disable
