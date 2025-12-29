# Claude Swarm

Run your own AI company. You're the CEO.

## Vision

```
┌─────────────────────────────────────────────────────────────┐
│                         YOU (CEO)                           │
│                    Set direction, oversee                   │
└─────────────────────────┬───────────────────────────────────┘
                          │
            ┌─────────────┴─────────────┐
            ▼                           ▼
    ┌───────────────┐           ┌───────────────┐
    │  Eng Manager  │           │ Product Mgr   │
    │   (Claude)    │           │   (Claude)    │
    └───────┬───────┘           └───────────────┘
            │
     ┌──────┼──────┐
     ▼      ▼      ▼
  ┌─────┐┌─────┐┌─────┐
  │Dev 1││Dev 2││Dev 3│   ← Work async, report up
  └─────┘└─────┘└─────┘
```

## How It Works

1. **You submit goals** → "Build user authentication"
2. **Manager breaks it down** → Creates tasks, assigns to devs
3. **Workers work async** → Each dev works independently
4. **Events bubble up** → Blocked? Question? You get notified
5. **You intervene when needed** → Answer questions, make decisions

## Quick Start

```bash
# 1. Start the Swarm app
cd electron-app && npm install && npm start

# 2. Configure MCP (add to ~/.mcp.json)
{
  "mcpServers": {
    "swarm": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "/path/to/claude-swarm/mcp-server", "python", "swarm_server.py"]
    }
  }
}

# 3. Start your Claude session and begin!
```

## CEO Commands

### Build Your Team
```python
# Hire an engineering manager
hire_worker(role="engineering_manager", name="Alice", directory="/project")

# Hire developers
hire_worker(role="developer", name="Bob", directory="/project")
hire_worker(role="developer", name="Carol", directory="/project")
```

### Submit Goals
```python
# Give your team a goal
submit_goal(
    goal="Build user authentication",
    description="We need login, logout, and password reset"
)
# Manager will break this down and delegate to devs
```

### Monitor Progress
```python
# Check organization status
get_org_status()

# See what needs your attention
get_notifications()

# Check blocked tasks
get_blocked_tasks()
```

### Respond to Your Team
```python
# Answer a question
respond_to_notification(notification_id="...", response="Use JWT tokens")

# Unblock a task
unblock_task(task_id="...", resolution="Approved, proceed with OAuth")

# Direct message
message_worker(worker_id="...", message="Great work on the API!")
```

## Available Roles

| Role | Description |
|------|-------------|
| `engineering_manager` | Breaks down goals, delegates to devs, reports progress |
| `developer` | Writes code, completes tasks, asks questions |
| `qa_engineer` | Tests code, reports bugs |

## Event Types

Events flow up the hierarchy until handled:

- **completed** - Task finished
- **blocked** - Worker stuck, needs help
- **question** - Worker has a question
- **escalation** - Needs CEO decision

## Architecture

```
claude-swarm/
├── core/                 # Core logic
│   ├── models.py         # Data models (Role, Task, Event, Worker)
│   ├── roles.py          # Role definitions (configurable)
│   ├── events.py         # Event bus for async communication
│   ├── tasks.py          # Task lifecycle management
│   └── swarm.py          # Main orchestrator
├── mcp-server/           # MCP server for Claude
│   └── swarm_server.py   # CEO-facing tools
└── electron-app/         # Desktop app (terminal UI)
```

## Customizing Roles

Create `~/.claude-swarm/roles/custom.yaml`:

```yaml
frontend_dev:
  name: "Frontend Developer"
  system_prompt: |
    You are a Frontend Developer specializing in React.
    Focus on UI/UX and component architecture.
  can_delegate: false
  reports_to: engineering_manager
  capabilities:
    - write_code
    - run_tests
```

## License

MIT
