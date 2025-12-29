"""
The Swarm - main orchestrator.

Coordinates workers, tasks, events, and roles.
This is the central brain of the organization.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import asdict

from .models import (
    Role, Task, TaskStatus, Event, EventType, Worker, Organization
)
from .roles import RoleManager
from .events import EventBus, worker_question, escalate_to_ceo
from .tasks import TaskManager


class Swarm:
    """
    The Swarm orchestrates an organization of Claude workers.

    Key responsibilities:
    - Manage worker lifecycle (create, assign roles, track status)
    - Route tasks through the hierarchy
    - Collect and route events
    - Persist state across sessions
    """

    def __init__(self, name: str = "My Organization", state_dir: Optional[Path] = None):
        self.name = name
        self.state_dir = state_dir or Path.home() / ".claude-swarm" / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Core components
        self.role_manager = RoleManager()
        self.event_bus = EventBus()
        self.task_manager = TaskManager(self.event_bus)

        # State
        self.workers: Dict[str, Worker] = {}
        self._conductor_api_url = "http://127.0.0.1:7422"

        # Load persisted state
        self._load_state()

    # =========================================================================
    # Worker Management
    # =========================================================================

    def hire_worker(
        self,
        role_id: str,
        name: str,
        directory: str,
        mcp_port: Optional[int] = None
    ) -> Optional[Worker]:
        """
        Create a new worker with a role.
        Returns the Worker object after the session is created.
        """
        role = self.role_manager.get_role(role_id)
        if not role:
            print(f"Unknown role: {role_id}")
            return None

        # Create session via Conductor API
        import urllib.request
        import urllib.error

        try:
            data = json.dumps({
                "name": f"{name} ({role.name})",
                "directory": directory,
                "role": "Worker",
                "mcp_port": mcp_port
            }).encode('utf-8')

            req = urllib.request.Request(
                f"{self._conductor_api_url}/sessions",
                data=data,
                method="POST",
                headers={"Content-Type": "application/json"}
            )

            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                session_id = result["id"]

                worker = Worker(
                    id=session_id,
                    role_id=role_id,
                    name=name,
                    directory=directory,
                    mcp_port=mcp_port,
                    status="idle"
                )
                self.workers[session_id] = worker
                self._save_state()

                # Send role system prompt to initialize the worker
                self._send_to_worker(session_id, f"""You are now assuming the role: {role.name}

{role.system_prompt}

You report to: {role.reports_to or 'CEO (the user)'}
Your capabilities: {', '.join(role.capabilities)}

Await your first task assignment.""")

                return worker

        except Exception as e:
            print(f"Failed to create worker: {e}")
            return None

    def fire_worker(self, worker_id: str) -> bool:
        """Remove a worker from the organization."""
        if worker_id not in self.workers:
            return False

        # Terminate session via API
        import urllib.request
        try:
            req = urllib.request.Request(
                f"{self._conductor_api_url}/sessions/{worker_id}",
                method="DELETE"
            )
            urllib.request.urlopen(req, timeout=10)
        except:
            pass  # Session might already be gone

        del self.workers[worker_id]
        self._save_state()
        return True

    def get_workers_by_role(self, role_id: str) -> List[Worker]:
        """Get all workers with a specific role."""
        return [w for w in self.workers.values() if w.role_id == role_id]

    def get_available_workers(self, role_id: Optional[str] = None) -> List[Worker]:
        """Get workers that are idle and available for tasks."""
        workers = self.workers.values()
        if role_id:
            workers = [w for w in workers if w.role_id == role_id]
        return [w for w in workers if w.status == "idle"]

    # =========================================================================
    # Task Flow
    # =========================================================================

    def submit_goal(self, goal: str, description: str = "") -> Task:
        """
        CEO submits a high-level goal.
        This gets routed to the appropriate manager.
        """
        # Create the top-level task
        task = self.task_manager.create_task(
            title=goal,
            description=description or goal,
            created_by="ceo",
            assigned_role="engineering_manager"  # Default to eng manager
        )

        # Find a manager to handle it
        managers = self.get_workers_by_role("engineering_manager")
        if managers:
            manager = managers[0]  # Use first available
            self.task_manager.assign_task(task.id, manager.id)

            # Send goal to manager
            self._send_to_worker(manager.id, f"""New goal from CEO:

**{goal}**

{description}

Please:
1. Break this down into specific tasks
2. Assign tasks to your team
3. Report back with your plan

Use these commands to manage tasks:
- Create subtasks for this goal
- Assign to available developers
- Monitor progress and report blockers""")

        return task

    def assign_task_to_worker(self, task_id: str, worker_id: str) -> bool:
        """Assign a task to a specific worker."""
        if worker_id not in self.workers:
            return False

        task = self.task_manager.get_task(task_id)
        if not task:
            return False

        worker = self.workers[worker_id]
        worker.status = "working"
        worker.current_task_id = task_id

        self.task_manager.assign_task(task_id, worker_id)
        self.task_manager.start_task(task_id)

        # Send task to worker
        self._send_to_worker(worker_id, f"""You have been assigned a task:

**{task.title}**

{task.description}

Please complete this task and report back when done.
If you're blocked or have questions, let me know.""")

        self._save_state()
        return True

    # =========================================================================
    # Event Handling
    # =========================================================================

    def report_completion(self, worker_id: str, output: str) -> bool:
        """Worker reports task completion."""
        worker = self.workers.get(worker_id)
        if not worker or not worker.current_task_id:
            return False

        self.task_manager.complete_task(worker.current_task_id, output)
        worker.status = "idle"
        worker.current_task_id = None
        self._save_state()
        return True

    def report_blocked(self, worker_id: str, reason: str, critical: bool = False) -> bool:
        """Worker reports being blocked."""
        worker = self.workers.get(worker_id)
        if not worker or not worker.current_task_id:
            return False

        worker.status = "blocked"
        self.task_manager.block_task(worker.current_task_id, reason, critical)
        self._save_state()
        return True

    def ask_question(self, worker_id: str, question: str) -> bool:
        """Worker asks a question."""
        worker = self.workers.get(worker_id)
        if not worker:
            return False

        task = self.task_manager.get_task(worker.current_task_id) if worker.current_task_id else None

        event = worker_question(
            task or Task(title="General question"),
            worker_id,
            question
        )
        event.source_role_id = worker.role_id
        self.event_bus.emit(event)
        return True

    def respond_to_event(self, event_id: str, response: str) -> bool:
        """CEO or manager responds to an event."""
        self.event_bus.mark_handled(event_id, "ceo", response)

        # Find the event and send response to the worker
        for event in self.event_bus.events:
            if event.id == event_id and event.source_worker_id:
                self._send_to_worker(event.source_worker_id, f"""Response to your question:

{response}

Please continue with your task.""")
                break

        return True

    # =========================================================================
    # Status & Reporting
    # =========================================================================

    def get_status(self) -> Dict[str, Any]:
        """Get current organization status for CEO dashboard."""
        return {
            "name": self.name,
            "workers": {
                w.id: {
                    "name": w.name,
                    "role": w.role_id,
                    "status": w.status,
                    "current_task": w.current_task_id
                }
                for w in self.workers.values()
            },
            "tasks": {
                "active": len(self.task_manager.get_active_tasks()),
                "blocked": len(self.task_manager.get_blocked_tasks()),
                "pending": len(self.task_manager.get_pending_tasks()),
            },
            "pending_notifications": len(self.event_bus.get_pending_for_ceo()),
            "recent_events": [
                {
                    "id": e.id,
                    "type": e.type.value,
                    "title": e.title,
                    "message": e.message[:200],
                    "requires_response": e.requires_response,
                    "handled": e.handled
                }
                for e in self.event_bus.get_recent_events(10)
            ]
        }

    def get_notifications(self) -> List[Dict[str, Any]]:
        """Get pending notifications for CEO."""
        return [
            {
                "id": e.id,
                "type": e.type.value,
                "title": e.title,
                "message": e.message,
                "task_id": e.task_id,
                "source_worker": e.source_worker_id,
                "created_at": e.created_at.isoformat(),
                "requires_response": e.requires_response
            }
            for e in self.event_bus.get_pending_for_ceo()
        ]

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _send_to_worker(self, worker_id: str, message: str) -> bool:
        """Send a message to a worker via Conductor API."""
        import urllib.request
        try:
            data = json.dumps({"message": message}).encode('utf-8')
            req = urllib.request.Request(
                f"{self._conductor_api_url}/sessions/{worker_id}/send",
                data=data,
                method="POST",
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=10)
            return True
        except Exception as e:
            print(f"Failed to send to worker: {e}")
            return False

    def _save_state(self) -> None:
        """Persist organization state."""
        state = {
            "name": self.name,
            "workers": {
                wid: {
                    "id": w.id,
                    "role_id": w.role_id,
                    "name": w.name,
                    "status": w.status,
                    "current_task_id": w.current_task_id,
                    "directory": w.directory,
                    "mcp_port": w.mcp_port
                }
                for wid, w in self.workers.items()
            },
            "tasks": {
                tid: {
                    "id": t.id,
                    "title": t.title,
                    "description": t.description,
                    "status": t.status.value,
                    "assigned_to": t.assigned_to,
                    "created_by": t.created_by,
                    "output": t.output
                }
                for tid, t in self.task_manager.tasks.items()
            }
        }
        state_file = self.state_dir / "swarm_state.json"
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2, default=str)

    def _load_state(self) -> None:
        """Load persisted organization state."""
        state_file = self.state_dir / "swarm_state.json"
        if not state_file.exists():
            return

        try:
            with open(state_file) as f:
                state = json.load(f)

            self.name = state.get("name", self.name)

            # Restore workers
            for wid, wdata in state.get("workers", {}).items():
                self.workers[wid] = Worker(
                    id=wdata["id"],
                    role_id=wdata["role_id"],
                    name=wdata["name"],
                    status=wdata.get("status", "offline"),
                    current_task_id=wdata.get("current_task_id"),
                    directory=wdata.get("directory"),
                    mcp_port=wdata.get("mcp_port")
                )

            # Restore tasks
            for tid, tdata in state.get("tasks", {}).items():
                task = Task(
                    id=tdata["id"],
                    title=tdata["title"],
                    description=tdata.get("description", ""),
                    status=TaskStatus(tdata.get("status", "pending")),
                    assigned_to=tdata.get("assigned_to"),
                    created_by=tdata.get("created_by"),
                    output=tdata.get("output")
                )
                self.task_manager.tasks[tid] = task

        except Exception as e:
            print(f"Failed to load state: {e}")
