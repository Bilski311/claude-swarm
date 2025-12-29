const { ipcRenderer } = require('electron');
const { Terminal } = require('@xterm/xterm');
const { FitAddon } = require('@xterm/addon-fit');

// State
const sessions = new Map(); // id -> { terminal, fitAddon, element }
let activeSessionId = null;
let gridCols = 2;

// DOM elements
const terminalGrid = document.getElementById('terminal-grid');
const conductorList = document.getElementById('conductor-list');
const workerList = document.getElementById('worker-list');
const sessionCount = document.getElementById('session-count');
const modal = document.getElementById('modal');
const addWorkerBtn = document.getElementById('add-worker-btn');
const modalCancel = document.getElementById('modal-cancel');
const modalCreate = document.getElementById('modal-create');
const sessionNameInput = document.getElementById('session-name');
const sessionDirInput = document.getElementById('session-dir');
const layoutBtns = document.querySelectorAll('.layout-btn');

// Create terminal pane
function createTerminalPane(id, name, role) {
  const pane = document.createElement('div');
  pane.className = 'terminal-pane';
  pane.id = `pane-${id}`;
  pane.innerHTML = `
    <div class="terminal-header">
      <span class="icon">${role === 'conductor' ? '🏠' : '⚡'}</span>
      <span class="name">${name}</span>
      <span class="status">
        <span class="status-dot working"></span>
        <span>Working</span>
      </span>
      ${role !== 'conductor' ? '<button class="close-btn">&times;</button>' : ''}
    </div>
    <div class="terminal-container" id="term-${id}"></div>
  `;

  // Handle close button
  const closeBtn = pane.querySelector('.close-btn');
  if (closeBtn) {
    closeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      ipcRenderer.send('delete-session', { id });
    });
  }

  // Handle click to focus
  pane.addEventListener('click', () => {
    setActiveSession(id);
  });

  terminalGrid.appendChild(pane);

  // Create terminal
  const terminal = new Terminal({
    cursorBlink: true,
    fontSize: 13,
    fontFamily: 'Menlo, Monaco, "Courier New", monospace',
    theme: {
      background: '#1a1a1a',
      foreground: '#ffffff',
      cursor: '#ffffff',
      cursorAccent: '#1a1a1a',
      selection: 'rgba(255, 255, 255, 0.3)'
    }
  });

  const fitAddon = new FitAddon();
  terminal.loadAddon(fitAddon);

  const termContainer = document.getElementById(`term-${id}`);
  terminal.open(termContainer);
  fitAddon.fit();

  // Handle input
  terminal.onData((data) => {
    ipcRenderer.send('terminal-input', { id, data });
  });

  // Handle resize
  const resizeObserver = new ResizeObserver(() => {
    fitAddon.fit();
    ipcRenderer.send('terminal-resize', {
      id,
      cols: terminal.cols,
      rows: terminal.rows
    });
  });
  resizeObserver.observe(termContainer);

  sessions.set(id, { terminal, fitAddon, element: pane, name, role, status: 'working' });

  updateSidebar();
  updateSessionCount();
  setActiveSession(id);
}

// Remove terminal pane
function removeTerminalPane(id) {
  const session = sessions.get(id);
  if (session) {
    session.terminal.dispose();
    session.element.remove();
    sessions.delete(id);
    updateSidebar();
    updateSessionCount();

    // Set active to first remaining session
    if (activeSessionId === id) {
      const firstSession = sessions.keys().next().value;
      if (firstSession) {
        setActiveSession(firstSession);
      }
    }
  }
}

// Update session status
function updateSessionStatus(id, status) {
  const session = sessions.get(id);
  if (session) {
    session.status = status;
    const pane = session.element;
    const statusDot = pane.querySelector('.status-dot');
    const statusText = pane.querySelector('.status span:last-child');

    statusDot.className = `status-dot ${status}`;
    statusText.textContent = status.charAt(0).toUpperCase() + status.slice(1);

    updateSidebar();
  }
}

// Set active session
function setActiveSession(id) {
  activeSessionId = id;

  // Update pane styles
  document.querySelectorAll('.terminal-pane').forEach(p => p.classList.remove('active'));
  const pane = document.getElementById(`pane-${id}`);
  if (pane) {
    pane.classList.add('active');
  }

  // Update sidebar
  document.querySelectorAll('.session-item').forEach(item => item.classList.remove('active'));
  const sidebarItem = document.querySelector(`.session-item[data-id="${id}"]`);
  if (sidebarItem) {
    sidebarItem.classList.add('active');
  }

  // Focus terminal
  const session = sessions.get(id);
  if (session) {
    session.terminal.focus();
  }
}

// Update sidebar
function updateSidebar() {
  conductorList.innerHTML = '';
  workerList.innerHTML = '';

  for (const [id, session] of sessions) {
    const item = document.createElement('div');
    item.className = `session-item ${id === activeSessionId ? 'active' : ''}`;
    item.dataset.id = id;
    item.innerHTML = `
      <span class="session-icon">${session.role === 'conductor' ? '🏠' : '⚡'}</span>
      <div class="session-info">
        <div class="session-name">${session.name}</div>
        <div class="session-status">${session.status}</div>
      </div>
      <span class="status-dot ${session.status}"></span>
    `;
    item.addEventListener('click', () => setActiveSession(id));

    if (session.role === 'conductor') {
      conductorList.appendChild(item);
    } else {
      workerList.appendChild(item);
    }
  }
}

// Update session count
function updateSessionCount() {
  sessionCount.textContent = `${sessions.size} Session${sessions.size !== 1 ? 's' : ''}`;
}

// Update grid layout
function setGridLayout(cols) {
  gridCols = cols;
  terminalGrid.className = `terminal-grid cols-${cols}`;
  layoutBtns.forEach(btn => {
    btn.classList.toggle('active', parseInt(btn.dataset.cols) === cols);
  });

  // Refit all terminals
  setTimeout(() => {
    for (const session of sessions.values()) {
      session.fitAddon.fit();
    }
  }, 100);
}

// IPC handlers
ipcRenderer.on('session-created', (event, data) => {
  createTerminalPane(data.id, data.name, data.role);
});

ipcRenderer.on('session-deleted', (event, data) => {
  removeTerminalPane(data.id);
});

ipcRenderer.on('session-exited', (event, data) => {
  updateSessionStatus(data.id, 'disconnected');
});

ipcRenderer.on('terminal-output', (event, data) => {
  const session = sessions.get(data.id);
  if (session) {
    session.terminal.write(data.data);
  }
});

// UI event handlers
layoutBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    setGridLayout(parseInt(btn.dataset.cols));
  });
});

addWorkerBtn.addEventListener('click', () => {
  sessionNameInput.value = '';
  sessionDirInput.value = '';
  modal.classList.remove('hidden');
  sessionNameInput.focus();
});

modalCancel.addEventListener('click', () => {
  modal.classList.add('hidden');
});

modalCreate.addEventListener('click', () => {
  const name = sessionNameInput.value.trim();
  const directory = sessionDirInput.value.trim();

  if (name && directory) {
    ipcRenderer.send('create-session', { name, directory, role: 'worker' });
    modal.classList.add('hidden');
  }
});

// Handle Enter in modal
sessionDirInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') {
    modalCreate.click();
  }
});

// Handle window resize
window.addEventListener('resize', () => {
  for (const session of sessions.values()) {
    session.fitAddon.fit();
  }
});

console.log('Claude Conductor renderer loaded');
