# VAEAGENT

VAEAGENT is a new multi-user Agent application with:

- Flutter cross-platform client source in `client/`
- FastAPI backend in `backend/`
- SQLite local storage for Windows 11 testing
- User registration/login with reserved email workflows
- Per-user sessions, messages, settings, tools, memory, tasks, and calendar data
- OpenRouter/OpenAI-compatible Chat Completions streaming with app-level NDJSON events
- User-configurable MCP servers with dynamic tool calling
- Markdown, LaTeX, image attachment, and `<bubble>` message support

## Backend

```powershell
cd path\to\VAEAGENT
pip install -r requirements.txt
$env:OPENROUTER_API_KEY="your-key"   # optional; without it the backend uses a local fallback reply
uvicorn backend.app.main:app --reload --port 8000
```

API base URL: `http://127.0.0.1:8000/api`

Useful endpoints:

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/sessions`
- `POST /api/sessions/new`
- `POST /api/chat/stream`
- `GET /api/tools`
- `GET /api/mcp/servers`
- `PUT /api/settings`

Run tests:

```powershell
pytest -q backend\tests
```

## Flutter Client

Flutter 3.44.4 has been installed at `C:\src\flutter`, and `C:\src\flutter\bin` has been added to the current user's PATH.

Open a new PowerShell window so PATH is refreshed, then run:

```powershell
cd path\to\VAEAGENT\client
flutter pub get
flutter run -d windows
```

The Windows platform project has already been generated. If `flutter build windows` reports that plugin builds require symlink support, enable Windows Developer Mode:

```powershell
start ms-settings:developers
```

The client defaults to `http://127.0.0.1:8000` and supports Simplified Chinese, Traditional Chinese, and English.

## Web Client And Cloudflare

The Flutter Web platform is enabled. Build the web app, then start FastAPI:

```powershell
cd path\to\VAEAGENT
.\scripts\build-web.ps1
.\scripts\run-backend.ps1
```

When `client/build/web` exists, FastAPI serves the web client from `/` and keeps the API under `/api`.

Copy `cloudflared-config.example.yml` to `cloudflared-config.yml`, then fill in your own tunnel ID, credentials path, and hostname. The local `cloudflared-config.yml` file is intentionally ignored by Git.
Start it with:

```powershell
.\run-tunnel.cmd
```

If Cloudflare DNS is not already routed to the existing tunnel, run the DNS route command from a Cloudflare-authenticated shell.

## Configuration

Edit `config/app.yaml` for default model, context cleanup, session carry-over, MCP, and default tool switches.
The current default model is OpenRouter `z-ai/glm-5.2` with provider routing `novita/fp8`.

Per-user settings can also be changed at runtime from the Flutter settings panel.

## MCP

Open settings in the client and add an MCP Server:

- `transport`: use `Streamable HTTP` for current HTTP MCP endpoints, or `SSE` for legacy compatible endpoints.
- `url`: the MCP endpoint, for example `http://127.0.0.1:9000/mcp`.
- `headers`: optional JSON object for authorization headers.

The backend calls `initialize`, `tools/list`, and `tools/call`, then exposes enabled MCP tools to the model during chat. `stdio` is reserved in the UI but not auto-executed in this MVP.
