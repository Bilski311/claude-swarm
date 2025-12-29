const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const http = require('http');
const pty = require('node-pty');
const os = require('os');
const fs = require('fs');

let mainWindow;
const sessions = new Map(); // id -> { pty, name, directory, role, status }
const CONFIG_DIR = path.join(os.homedir(), '.claude-swarm');
const SESSIONS_FILE = path.join(CONFIG_DIR, 'sessions.json');

// Role-specific system prompts
const ROLE_PROMPTS = {
  engineering_manager: `You are an Engineering Manager in a software development organization.

Your responsibilities:
- Receive high-level goals from the CEO/leadership
- Break down goals into concrete, actionable tasks
- Assign tasks to your team of developers
- Monitor progress and unblock your team
- Escalate issues that need CEO attention
- Report completions and summarize outcomes

When you receive a goal:
1. Analyze what needs to be done
2. Break it into 2-5 specific tasks
3. Create tasks and assign to available developers
4. Monitor for blockers or questions

When a developer is blocked or has a question:
- Try to unblock them yourself if possible
- Escalate to CEO if it requires a business decision

Always be proactive about status updates.`,

  developer: `You are a Software Developer working on assigned tasks.

Your responsibilities:
- Complete assigned development tasks
- Write clean, tested code
- Report progress and blockers
- Ask questions when requirements are unclear

When you receive a task:
1. Understand the requirements
2. Plan your approach
3. Implement the solution
4. Report completion with a summary

If you're blocked:
- Clearly describe what's blocking you
- Suggest possible solutions if you have ideas

If you have a question:
- Be specific about what you need to know

Always update your status as you work.`,

  qa_engineer: `You are a QA Engineer responsible for testing and quality.

Your responsibilities:
- Review code changes for quality
- Write and run tests
- Report bugs and issues
- Verify fixes

Be thorough but pragmatic about testing.`
};

// Ensure config directory exists
if (!fs.existsSync(CONFIG_DIR)) {
  fs.mkdirSync(CONFIG_DIR, { recursive: true });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    },
    title: 'Claude Swarm'
  });

  mainWindow.loadFile('index.html');

  // Load saved sessions on startup
  loadSessions();
}

function loadSessions() {
  try {
    if (fs.existsSync(SESSIONS_FILE)) {
      const data = JSON.parse(fs.readFileSync(SESSIONS_FILE, 'utf8'));
      mainWindow.webContents.once('did-finish-load', () => {
        // Restore saved worker sessions
        const workers = data.filter(s => s.role === 'Worker');

        // Restore workers with slight delays to avoid overwhelming
        workers.forEach((worker, index) => {
          setTimeout(() => {
            createSession(worker.id, worker.name, worker.directory, worker.role, worker.mcpPort);
          }, index * 500);
        });
      });
    }
    // No auto-created sessions - CEO hires workers via Dashboard or MCP tools
  } catch (e) {
    console.error('Failed to load sessions:', e);
  }
}

function saveSessions() {
  const data = Array.from(sessions.entries()).map(([id, s]) => ({
    id,
    name: s.name,
    directory: s.directory,
    role: s.role
  }));
  fs.writeFileSync(SESSIONS_FILE, JSON.stringify(data, null, 2));
}

function createSession(id, name, directory, role = 'Worker', mcpPort = null, roleId = null) {
  const sessionId = id || require('crypto').randomUUID();

  const shell = process.env.SHELL || '/bin/zsh';
  const claudeCmd = 'claude';

  // Environment setup
  const env = { ...process.env };
  env.TERM = 'xterm-256color';
  env.COLORTERM = 'truecolor';

  // Set Unreal MCP port if specified (for multi-UE-instance support)
  if (mcpPort) {
    env.MCP_UE_PORT = String(mcpPort);
  }

  // Add paths
  const additionalPaths = [
    '/opt/homebrew/bin',
    '/usr/local/bin',
    path.join(os.homedir(), '.local/bin'),
    path.join(os.homedir(), '.npm-global/bin'),
    path.join(os.homedir(), '.nvm/versions/node/v22.11.0/bin')
  ];
  env.PATH = additionalPaths.join(':') + ':' + (env.PATH || '/usr/bin:/bin');

  const ptyProcess = pty.spawn(shell, ['-c', `cd '${directory}' && ${claudeCmd}`], {
    name: 'xterm-256color',
    cols: 120,
    rows: 30,
    cwd: directory,
    env
  });

  sessions.set(sessionId, {
    pty: ptyProcess,
    name,
    directory,
    role,
    roleId,
    mcpPort,
    status: 'working',
    outputBuffer: ''  // Store terminal output for API access
  });

  // Inject role prompt after Claude starts (wait for ready)
  if (roleId && ROLE_PROMPTS[roleId]) {
    const rolePrompt = ROLE_PROMPTS[roleId];
    // Wait a bit for Claude to initialize, then send the role context
    setTimeout(() => {
      const introMessage = `[SYSTEM CONTEXT] ${rolePrompt}\n\nAcknowledge your role briefly and wait for your first task.`;
      ptyProcess.write(introMessage + '\r');
    }, 3000);  // Wait 3 seconds for Claude to start
  }

  // Forward PTY output to renderer AND store in buffer
  ptyProcess.onData((data) => {
    const session = sessions.get(sessionId);
    if (session) {
      // Keep last 50KB of output
      session.outputBuffer = (session.outputBuffer + data).slice(-50000);
    }
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('terminal-output', { id: sessionId, data });
    }
  });

  ptyProcess.onExit(() => {
    const session = sessions.get(sessionId);
    if (session) {
      session.status = 'disconnected';
    }
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('session-exited', { id: sessionId });
    }
  });

  // Notify renderer of new session
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('session-created', {
      id: sessionId,
      name,
      directory,
      role,
      status: 'working'
    });
  }

  saveSessions();

  // Auto-confirm MCP prompts - send Enter multiple times with delays
  // First Enter after 2s, second after 4s to catch MCP confirmation
  setTimeout(() => {
    if (sessions.has(sessionId)) {
      ptyProcess.write('\r');
    }
  }, 2000);

  setTimeout(() => {
    if (sessions.has(sessionId)) {
      ptyProcess.write('\r');
    }
  }, 4000);

  setTimeout(() => {
    if (sessions.has(sessionId)) {
      ptyProcess.write('\r');
    }
  }, 6000);

  return sessionId;
}

function deleteSession(id) {
  const session = sessions.get(id);
  if (session) {
    session.pty.kill();
    sessions.delete(id);
    saveSessions();

    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('session-deleted', { id });
    }
    return true;
  }
  return false;
}

// IPC handlers
ipcMain.on('terminal-input', (event, { id, data }) => {
  const session = sessions.get(id);
  if (session) {
    session.pty.write(data);
  }
});

ipcMain.on('terminal-resize', (event, { id, cols, rows }) => {
  const session = sessions.get(id);
  if (session) {
    session.pty.resize(cols, rows);
  }
});

ipcMain.on('create-session', (event, { name, directory, role }) => {
  createSession(null, name, directory, role);
});

ipcMain.on('delete-session', (event, { id }) => {
  deleteSession(id);
});

// Directory picker dialog
ipcMain.handle('show-directory-picker', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
    title: 'Select Working Directory'
  });
  if (!result.canceled && result.filePaths.length > 0) {
    return result.filePaths[0];
  }
  return null;
});

// HTTP API for MCP communication (port 7422)
const httpServer = http.createServer((req, res) => {
  let body = '';
  req.on('data', chunk => body += chunk);
  req.on('end', () => {
    const url = new URL(req.url, 'http://localhost');
    const path = url.pathname;

    res.setHeader('Content-Type', 'application/json');

    try {
      // GET /sessions - list all sessions
      if (req.method === 'GET' && path === '/sessions') {
        const sessionList = Array.from(sessions.entries()).map(([id, s]) => ({
          id,
          name: s.name,
          directory: s.directory,
          role: s.role,
          mcpPort: s.mcpPort,
          status: s.status
        }));
        res.writeHead(200);
        res.end(JSON.stringify({ sessions: sessionList, count: sessionList.length }));
        return;
      }

      // POST /sessions - create new session
      if (req.method === 'POST' && path === '/sessions') {
        const data = JSON.parse(body || '{}');
        if (!data.name || !data.directory) {
          res.writeHead(400);
          res.end(JSON.stringify({ error: 'Missing name or directory' }));
          return;
        }
        const mcpPort = data.mcp_port || null;
        const roleId = data.role_id || null;  // e.g., "engineering_manager", "developer"
        const id = createSession(null, data.name, data.directory, data.role || 'Worker', mcpPort, roleId);
        res.writeHead(201);
        res.end(JSON.stringify({ id, name: data.name, role_id: roleId, mcp_port: mcpPort, status: 'created' }));
        return;
      }

      // POST /sessions/:id/send - send input to session
      const sendMatch = path.match(/^\/sessions\/([^/]+)\/send$/);
      if (req.method === 'POST' && sendMatch) {
        const id = sendMatch[1];
        const data = JSON.parse(body || '{}');
        const session = sessions.get(id);
        if (session && data.message) {
          // Write the message first
          session.pty.write(data.message);
          // Then send Enter separately after a short delay
          setTimeout(() => {
            session.pty.write('\r');
          }, 100);
          res.writeHead(200);
          res.end(JSON.stringify({ status: 'sent', id }));
        } else {
          res.writeHead(400);
          res.end(JSON.stringify({ error: 'Invalid session or message' }));
        }
        return;
      }

      // GET /sessions/:id/output - get session output
      const outputMatch = path.match(/^\/sessions\/([^/]+)\/output$/);
      if (req.method === 'GET' && outputMatch) {
        const id = outputMatch[1];
        const session = sessions.get(id);
        if (session) {
          res.writeHead(200);
          res.end(JSON.stringify({
            id,
            name: session.name,
            status: session.status,
            output: session.outputBuffer || ''
          }));
        } else {
          res.writeHead(404);
          res.end(JSON.stringify({ error: 'Session not found' }));
        }
        return;
      }

      // DELETE /sessions/:id - delete session
      const deleteMatch = path.match(/^\/sessions\/([^/]+)$/);
      if (req.method === 'DELETE' && deleteMatch) {
        const id = deleteMatch[1];
        if (deleteSession(id)) {
          res.writeHead(200);
          res.end(JSON.stringify({ status: 'deleted', id }));
        } else {
          res.writeHead(404);
          res.end(JSON.stringify({ error: 'Session not found' }));
        }
        return;
      }

      res.writeHead(404);
      res.end(JSON.stringify({ error: 'Not found' }));

    } catch (e) {
      console.error('HTTP error:', e);
      res.writeHead(500);
      res.end(JSON.stringify({ error: e.message }));
    }
  });
});

app.whenReady().then(() => {
  createWindow();

  httpServer.listen(7422, '127.0.0.1', () => {
    console.log('HTTP API listening on port 7422');
  });
});

app.on('window-all-closed', () => {
  // Kill all PTY processes
  for (const [id, session] of sessions) {
    session.pty.kill();
  }
  httpServer.close();
  app.quit();
});
