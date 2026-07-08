# Tool Workflow

Use this skill when a user asks the Agent to create tasks, remember facts, manage calendar items, request structured input, confirm an action, or call a custom MCP tool.

Rules:
- Prefer native tool calls when the model/provider supports them.
- If native tool calls are unavailable, emit one compact XML block:

```xml
<function_calls>
  <invoke name="tool_name">
    <parameter name="param_name">value</parameter>
  </invoke>
</function_calls>
```

- Do not tell the user that a tool succeeded until the runtime returns a `tool_result`.
- If a tool returns `pending: true`, stop and wait for the user to fill the UI request or confirm the action.
- After a non-pending tool result, continue the answer using the returned data.
