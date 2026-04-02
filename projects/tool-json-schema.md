# Tool JSON Schema - Implementation Proposal

## Overview

Currently OpenClaw tools use natural language descriptions. This proposal adds optional JSON Schema support via the OpenClaw tool layer (no core changes needed).

## Key Finding

TypeBox (used internally) has built-in JSON Schema export:
```javascript
import { Type, type TSchema } from "@sinclair/typebox";
const jsonSchema = Type.Schema(schema);  // One-line conversion
```

## Architecture

```
OpenClaw Plugin
    │
    ├── ToolDefinition (TypeBox TSchema)
    │         │
    │         ▼
    │   typeBoxToJsonSchema()  ← NEW utility
    │         │
    │         ▼
    │   { jsonSchema: {...}   ← Add to tool output
    │
    ▼
pi-coding-agent (unchanged)
```

## Implementation Steps

### Step 1: Create utility

Create `/path/to/tool-schema-utils.ts`:

```typescript
import { Type, type TSchema } from "@sinclair/typebox";

/**
 * Convert TypeBox TSchema to standard JSON Schema
 * TypeBox natively supports: Type.Schema()
 */
export function typeBoxToJsonSchema(schema: TSchema): Record<string, unknown> {
  return Type.Schema(schema) as Record<string, unknown>;
}

/**
 * Create tool definition with JSON Schema output
 */
export function createToolWithSchema(tool: AnyAgentTool): AnyAgentTool & { jsonSchema: Record<string, unknown> } {
  return {
    ...tool,
    jsonSchema: typeBoxToJsonSchema(tool.parameters)
  };
}
```

### Step 2: Modify toToolDefinitions

In the OpenClaw tool adapter layer:

```typescript
import { typeBoxToJsonSchema } from "./tool-schema-utils";

export function toToolDefinitions(tools: AnyAgentTool[]): ToolDefinition[] {
  return tools.map((tool) => {
    const def = createToolDefinitionFromAgentTool(tool);
    // Auto-generate JSON Schema
    def.jsonSchema = typeBoxToJsonSchema(tool.parameters);
    return def;
  });
}
```

### Step 3: Use in Hooks/Plugins

```javascript
api.registerHook("before_tool_call", async ({ event, ctx }) => {
  // Access JSON Schema for validation
  const schema = event.tool.jsonSchema;
  const isValid = validateAgainstSchema(event.tool.params, schema);
  if (!isValid) {
    return { block: true, reason: "Invalid parameters" };
  }
  return {};
});
```

## Verification

After implementation, verify with:

```bash
# Check a tool's schema
curl -s http://localhost:18789/api/tools/read | jq '.jsonSchema'
```

Should return:
```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string" },
    "offset": { "type": "integer" },
    "limit": { "type": "integer" }
  },
  "required": ["path"]
}
```

## Benefits

| Benefit | Description |
|---------|-------------|
| LLM Tool Calling | Better parameter inference with JSON Schema |
| Validation | Hooks can validate before execution |
| Documentation | Auto-generate API docs |
| Interop | JSON Schema is universal standard |

## Effort

- Utility function: 30 min
- Integration: 1-2 hours  
- Testing: 2-3 hours
- **Total: Half a day**

## Files to Modify

1. `tool-schema-utils.ts` (NEW)
2. Tool adapter in OpenClaw extensions layer

## Status

**Ready to implement** - no core changes required.
