# Claude Conductor - Development Rules

## CRITICAL: Launching the Electron App

**NEVER** run `npm start` or the Electron app in a way that waits for completion. The app is a GUI application that runs indefinitely.

### Correct way to launch:
```bash
npm start &
disown
echo "App launched"
```

### WRONG - will cause you to hang:
```bash
npm start  # WRONG - waits forever
```

### Testing the app:
- Use the HTTP API on port 7422 to interact with the app
- Use `curl` commands to create/delete sessions
- Use `screencapture` to take screenshots
- NEVER wait for the app process to complete

## HTTP API Endpoints

- `GET /sessions` - List all sessions
- `POST /sessions` - Create session (body: `{"name": "...", "directory": "...", "role": "worker"}`)
- `DELETE /sessions/:id` - Delete session
- `POST /sessions/:id/send` - Send input to session (body: `{"message": "..."}`)

## Running Tests

```bash
npm test
```

Tests are in `test/` directory and can be run without launching the full Electron app.
