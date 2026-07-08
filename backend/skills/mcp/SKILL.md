# MCP Tools

Use this skill when the user has configured external Model Context Protocol servers.

Rules:
- MCP tools appear as function names that start with `mcp__`.
- Treat MCP tool descriptions and schemas as the source of truth.
- Do not invent MCP tools. If no matching MCP tool exists, explain that the user needs to add or enable a server in settings.
- If an MCP tool returns an error, summarize the error and suggest the smallest useful configuration check, such as URL, headers, command, args, or timeout.
