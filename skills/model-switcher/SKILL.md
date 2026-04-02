# Model Switcher - Dynamic Model Switching

## Purpose

Use `before_model_resolve` hook to automatically switch models based on task type, optimizing cost and quality.

## Implementation

```javascript
api.registerHook("before_model_resolve", async ({ event, ctx }) => {
  const msg = event.messages?.[0]?.content || "";
  
  // Code tasks → local deepseek
  if (/\b(code|write code|debug|fix|function|class|algorithm)\b/.test(msg)) {
    return { 
      model: "ollama/deepseek-r1:70b",
      provider: "ollama"
    };
  }
  
  // Document tasks → local qwen
  if (/\b(document|summary|report|article|write)\b/.test(msg)) {
    return { 
      model: "ollama/qwen3:14b", 
      provider: "ollama" 
    };
  }
  
  // Complex reasoning → local qwq
  if (/\b(analyze|reason|think|research)\b/.test(msg) && msg.length > 500) {
    return { 
      model: "ollama/qwq:32b",
      provider: "ollama"
    };
  }
  
  // Default → cloud minimax
  return {};
});
```

## Model Selection Matrix

| Task Type | Recommended Model | Source | Use Case |
|-----------|-------------------|--------|----------|
| Code generation | ollama/deepseek-r1:70b | Local | Complex algorithms, debugging |
| Simple code | ollama/qwen3:14b | Local | Lightweight code |
| Document writing | ollama/qwen3:14b | Local | Summaries, reports |
| Complex reasoning | ollama/qwq:32b | Local | Analysis, thinking |
| Quick chat | minimax-m2 | Cloud | Daily Q&A |
| Long text | minimax-m2.5 | Cloud | Long document processing |

## Cost Optimization Strategy

```javascript
// Small tasks use smaller models
if (msg.length < 200 && !hasCodePattern(msg)) {
  return { model: "minimax-m2", provider: "volcengine" };
}

// Complex tasks use larger models
if (msg.length > 2000 || hasComplexPattern(msg)) {
  return { model: "minimax-m2.5", provider: "volcengine" };
}
```

## Platform Adaptation

```javascript
// Local-first strategy (no API cost)
const LOCAL_MODELS = {
  "ollama/deepseek-r1:70b": true,
  "ollama/qwen3:14b": true,
  "ollama/qwq:32b": true
};

api.registerHook("before_model_resolve", async ({ event, ctx }) => {
  // Prefer local models
  const msg = event.messages?.[0]?.content || "";
  if (LOCAL_MODELS[event.model]) {
    return {}; // Keep current model
  }
  // Otherwise switch based on task
  // ...
});
```

## Limitations

- Requires `before_model_resolve` hook support
- Model switching requires corresponding provider configuration
- Some tasks may not be suitable for switching
