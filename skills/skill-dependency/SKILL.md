# Skill Dependency - Skill Dependency Chain

## Current Status: Limited Support

OpenClaw's Skill system **does not natively support** explicit skill-to-skill invocation chains. However, there are several indirect ways to achieve skill composition.

## Method 1: Via Read Tool

An agent can actively read another skill's SKILL.md:

```
When a skill needs functionality from another skill,
instruct the agent:
"To use GitHub operations, first read $SKILL_HOME/github/SKILL.md"
```

## Method 2: Skill Description References

Reference other skills in a skill's description:

```markdown
---
name: my-combination-skill
description: Combined task handling, integrating GitHub and Shell operations
---

This skill handles complex tasks requiring multiple tools.
```

## Method 3: Shared Tools

Multiple skills can register the same tool, differentiating usage via tool descriptions.

## Method 4: Subagent Composition

A skill can call sessions_spawn to spawn subagents:

```
Note: Be aware of subagent tool restrictions.
```

## Unsupported Features

❌ Skill calls Skill (no call stack)  
❌ Skill inheritance (no extends)  
❌ Skill dependency declaration (no package.json style)  
❌ Auto-trigger chains (no onComplete hook)  

## Best Practices

1. **Atomic design**: Each skill focuses on a single responsibility
2. **Clear descriptions**: Explain relationships with other skills in the description
3. **Shared code**: If shared logic is needed, consider creating a shared module
4. **Documentation**: Explain required dependencies in SKILL.md

## Example: Composite Skill

```markdown
---
name: full-stack-dev
description: Full-stack development tasks, combining code and deploy skills
---

# Full Stack Developer

Handles complete development task flows.

## Workflow

1. Use `coding-skill` to generate code
2. Use `shell-skill` to run tests
3. Use `deploy-skill` to deploy

## Dependencies

- coding-skill: $SKILL_HOME/coding/SKILL.md
- shell-skill: $SKILL_HOME/shell/SKILL.md
- deploy-skill: $SKILL_HOME/deploy/SKILL.md

## Usage

When needed, I will read the relevant skill's SKILL.md to execute specific operations.
```
