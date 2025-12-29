/**
 * CEO Dashboard - Real-time view of your AI organization
 * Note: ipcRenderer is available from renderer.js which loads first
 */

const SWARM_API = 'http://127.0.0.1:7423';  // Swarm state API (different from conductor)
const POLL_INTERVAL = 3000;  // Poll every 3 seconds

// State
let currentNotificationId = null;
let pollTimer = null;

// =============================================================================
// View Switching
// =============================================================================

document.querySelectorAll('.view-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const view = tab.dataset.view;

    // Update tabs
    document.querySelectorAll('.view-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');

    // Update views
    document.getElementById('dashboard-view').classList.toggle('active', view === 'dashboard');
    document.getElementById('terminal-view').classList.toggle('active', view === 'terminals');
  });
});

// =============================================================================
// Hire Worker Modal
// =============================================================================

document.getElementById('hire-btn').addEventListener('click', () => {
  document.getElementById('hire-modal').classList.remove('hidden');
});

document.getElementById('hire-cancel').addEventListener('click', () => {
  document.getElementById('hire-modal').classList.add('hidden');
});

document.getElementById('hire-browse').addEventListener('click', async () => {
  const path = await ipcRenderer.invoke('show-directory-picker');
  if (path) {
    document.getElementById('hire-dir').value = path;
  }
});

document.getElementById('hire-confirm').addEventListener('click', async () => {
  const role = document.getElementById('hire-role').value;
  const name = document.getElementById('hire-name').value;
  const directory = document.getElementById('hire-dir').value;

  if (!name || !directory) {
    alert('Please fill in all fields');
    return;
  }

  // Create worker with role-specific system prompt
  try {
    const resp = await fetch('http://127.0.0.1:7422/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: `${name} (${role})`,
        directory: directory,
        role: 'Worker',
        role_id: role  // This triggers the role-specific prompt injection
      })
    });

    if (resp.ok) {
      document.getElementById('hire-modal').classList.add('hidden');
      document.getElementById('hire-name').value = '';
      document.getElementById('hire-dir').value = '';
      refreshDashboard();
    }
  } catch (e) {
    console.error('Failed to hire worker:', e);
  }
});

// =============================================================================
// Respond Modal
// =============================================================================

function showRespondModal(notification) {
  currentNotificationId = notification.id;
  document.getElementById('respond-title').textContent = notification.title;
  document.getElementById('respond-context').textContent = notification.message;
  document.getElementById('respond-input').value = '';
  document.getElementById('respond-modal').classList.remove('hidden');
}

document.getElementById('respond-cancel').addEventListener('click', () => {
  document.getElementById('respond-modal').classList.add('hidden');
  currentNotificationId = null;
});

document.getElementById('respond-send').addEventListener('click', async () => {
  const response = document.getElementById('respond-input').value;
  if (!response.trim()) {
    alert('Please enter a response');
    return;
  }

  // Send response via worker message
  // In a real implementation, this would go through the Swarm API
  console.log('Sending response:', currentNotificationId, response);

  document.getElementById('respond-modal').classList.add('hidden');
  currentNotificationId = null;
  refreshDashboard();
});

// =============================================================================
// Dashboard Data
// =============================================================================

async function refreshDashboard() {
  try {
    // Fetch from conductor API (sessions)
    const sessionsResp = await fetch('http://127.0.0.1:7422/sessions');
    const sessionsData = await sessionsResp.json();

    const workers = sessionsData.sessions.filter(s => s.role === 'Worker');

    // Update stats
    document.getElementById('stat-workers').textContent = workers.length;
    document.getElementById('session-count').textContent = `${workers.length} workers`;

    // For now, use mock data for tasks and notifications
    // In full implementation, this comes from Swarm state API
    updateWorkersList(workers);
    updateNotificationBadge(0);  // Will be populated when events occur

  } catch (e) {
    console.error('Failed to refresh dashboard:', e);
  }
}

function updateWorkersList(workers) {
  const container = document.getElementById('worker-list-dashboard');
  const count = document.getElementById('workers-count');

  count.textContent = workers.length;

  if (workers.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">👤</div>
        <div class="empty-state-title">No workers yet</div>
        <div>Hire your first worker to begin</div>
      </div>
    `;
    return;
  }

  container.innerHTML = workers.map(w => {
    const emoji = getWorkerEmoji(w.name);
    const role = extractRole(w.name);
    const status = w.status || 'idle';

    return `
      <div class="worker-item">
        <div class="worker-avatar">${emoji}</div>
        <div class="worker-info">
          <div class="worker-name">${extractName(w.name)}</div>
          <div class="worker-role">${role}</div>
        </div>
        <span class="worker-status ${status}">${status}</span>
      </div>
    `;
  }).join('');
}

function updateNotificationsList(notifications) {
  const container = document.getElementById('notification-list');
  const count = document.getElementById('notifications-count');

  count.textContent = notifications.length;
  document.getElementById('stat-notifications').textContent = notifications.length;

  if (notifications.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">✅</div>
        <div class="empty-state-title">All clear!</div>
        <div>No notifications need your attention</div>
      </div>
    `;
    return;
  }

  container.innerHTML = notifications.map(n => {
    const typeClass = n.type.toLowerCase();
    return `
      <div class="notification-item ${typeClass}" data-id="${n.id}">
        <div class="notification-header">
          <span class="notification-type ${typeClass}">${n.type}</span>
          <span class="notification-time">${formatTime(n.created_at)}</span>
        </div>
        <div class="notification-title">${n.title}</div>
        <div class="notification-message">${n.message}</div>
        ${n.requires_response ? `
          <div class="notification-actions">
            <button class="btn" onclick="showRespondModal(${JSON.stringify(n).replace(/"/g, '&quot;')})">Respond</button>
          </div>
        ` : ''}
      </div>
    `;
  }).join('');
}

function updateTasksList(tasks) {
  const container = document.getElementById('task-list');
  const count = document.getElementById('tasks-count');

  count.textContent = tasks.length;
  document.getElementById('stat-active').textContent = tasks.filter(t => t.status === 'in_progress').length;
  document.getElementById('stat-blocked').textContent = tasks.filter(t => t.status === 'blocked').length;

  if (tasks.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">📝</div>
        <div class="empty-state-title">No active tasks</div>
        <div>Submit a goal to get started</div>
      </div>
    `;
    return;
  }

  container.innerHTML = tasks.map(t => {
    const statusIcon = t.status === 'completed' ? '✓' :
                       t.status === 'blocked' ? '!' : '';
    return `
      <div class="task-item">
        <div class="task-status-icon ${t.status}">${statusIcon}</div>
        <div class="task-title">${t.title}</div>
        <div class="task-assignee">${t.assigned_to || 'Unassigned'}</div>
      </div>
    `;
  }).join('');
}

function updateNotificationBadge(count) {
  const badge = document.getElementById('notification-count');
  if (count > 0) {
    badge.textContent = count;
    badge.style.display = 'inline';
  } else {
    badge.style.display = 'none';
  }
}

// =============================================================================
// Helpers
// =============================================================================

function getWorkerEmoji(name) {
  const nameLower = name.toLowerCase();
  if (nameLower.includes('manager')) return '👔';
  if (nameLower.includes('qa') || nameLower.includes('test')) return '🔍';
  if (nameLower.includes('dev')) return '💻';
  return '👤';
}

function extractRole(name) {
  // Extract role from name like "Alice (Engineering Manager)"
  const match = name.match(/\(([^)]+)\)/);
  return match ? match[1] : 'Worker';
}

function extractName(name) {
  // Extract just the name part
  return name.replace(/\s*\([^)]+\)\s*/, '').trim();
}

function formatTime(isoString) {
  if (!isoString) return '';
  const date = new Date(isoString);
  const now = new Date();
  const diff = now - date;

  if (diff < 60000) return 'just now';
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  return date.toLocaleDateString();
}

// =============================================================================
// Initialize
// =============================================================================

// Start polling
function startPolling() {
  refreshDashboard();
  pollTimer = setInterval(refreshDashboard, POLL_INTERVAL);
}

// Initial load
document.addEventListener('DOMContentLoaded', () => {
  startPolling();
});

// Expose for onclick handlers
window.showRespondModal = showRespondModal;
