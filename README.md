# Claude Swarm

Orchestrate multiple Claude Code sessions for parallel AI development.

## Overview

Claude Swarm lets a "conductor" Claude manage multiple "worker" Claudes, enabling:
- Parallel task execution across multiple codebases
- Coordinated multi-agent workflows
- Real-time visibility into all worker sessions

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Claude Swarm App                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │Conductor │  │ Worker 1 │  │ Worker 2 │  │ Worker N │    │
│  │ (Claude) │  │ (Claude) │  │ (Claude) │  │ (Claude) │    │
│  └────┬─────┘  └──────────┘  └──────────┘  └──────────┘    │
│       │                                                      │
│       │ MCP Tools                                            │
│       ▼                                                      │
│  ┌──────────┐                                               │
│  │   MCP    │ ◄─── create_worker, send_to_worker,          │
│  │  Server  │      wait_for_workers, etc.                   │
│  └────┬─────┘                                               │
│       │ HTTP API (:7422)                                    │
│       ▼                                                      │
│  ┌──────────┐                                               │
│  │ Electron │ ◄─── Session management, PTY, UI              │
│  │   Main   │                                               │
│  └──────────┘                                               │
└─────────────────────────────────────────────────────────────┘
```

## Installation

```bash
cd electron-app
npm install
npm run build
# Install to Applications
cp -r "dist/mac-arm64/Claude Swarm.app" /Applications/
```

## MCP Server Setup

Add to your `~/.mcp.json`:

```json
{
  "mcpServers": {
    "conductor": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "/path/to/claude-swarm/mcp-server", "python", "conductor_server.py"]
    }
  }
}
```

## Usage

### Basic Workflow

```python
# 1. Create workers
api_worker = create_worker(name="api-research", directory="/project")
ui_worker = create_worker(name="ui-research", directory="/project")

# 2. Send tasks
send_to_worker(api_worker["id"], "Analyze the API structure...")
send_to_worker(ui_worker["id"], "Review the UI components...")

# 3. Wait and collect results
results = wait_for_workers(timeout_seconds=180)

# 4. Synthesize outputs
# Now you have results from both workers to combine
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `create_worker(name, directory)` | Create a new worker session |
| `send_to_worker(worker_id, message)` | Send task to specific worker |
| `broadcast_to_workers(message)` | Send to all workers |
| `wait_for_workers(timeout)` | Wait for workers to complete |
| `get_worker_output(worker_id)` | Get output from worker |
| `get_all_outputs()` | Get all outputs immediately |
| `list_workers()` | List active sessions |
| `terminate_worker(worker_id)` | Remove a worker |

## Development

```bash
cd electron-app
npm start  # Run in development
npm test   # Run tests
```

## License

MIT
