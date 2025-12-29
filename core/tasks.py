"""
Task management system.

Tasks flow from CEO → Manager → Workers.
Workers report completion back up the chain.
"""

from datetime import datetime
from typing import Dict, List, Optional
from .models import Task, TaskStatus, Worker, Event, EventType
from .events import EventBus, task_completed, worker_blocked


class TaskManager:
    """
    Manages task lifecycle - creation, assignment, completion.
    """

    def __init__(self, event_bus: EventBus):
        self.tasks: Dict[str, Task] = {}
        self.event_bus = event_bus

    def create_task(
        self,
        title: str,
        description: str,
        created_by: str,
        parent_task_id: Optional[str] = None,
        assigned_role: Optional[str] = None,
    ) -> Task:
        """Create a new task."""
        task = Task(
            title=title,
            description=description,
            created_by=created_by,
            parent_task_id=parent_task_id,
            assigned_role=assigned_role,
        )
        self.tasks[task.id] = task

        # Link to parent if exists
        if parent_task_id and parent_task_id in self.tasks:
            self.tasks[parent_task_id].subtask_ids.append(task.id)

        # Emit event
        self.event_bus.emit(Event(
            type=EventType.TASK_CREATED,
            task_id=task.id,
            title=f"New task: {title}",
            message=description,
            data={"created_by": created_by, "assigned_role": assigned_role}
        ))

        return task

    def assign_task(self, task_id: str, worker_id: str) -> bool:
        """Assign a task to a worker."""
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        task.assigned_to = worker_id
        task.status = TaskStatus.PENDING

        self.event_bus.emit(Event(
            type=EventType.DELEGATION,
            task_id=task_id,
            title=f"Task assigned: {task.title}",
            message=f"Assigned to worker {worker_id}",
            data={"worker_id": worker_id}
        ))

        return True

    def start_task(self, task_id: str) -> bool:
        """Mark task as started."""
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now()

        self.event_bus.emit(Event(
            type=EventType.TASK_STARTED,
            task_id=task_id,
            title=f"Started: {task.title}",
            source_worker_id=task.assigned_to
        ))

        return True

    def complete_task(self, task_id: str, output: str) -> bool:
        """Mark task as completed with output."""
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now()
        task.output = output

        # Emit completion event
        self.event_bus.emit(task_completed(task, task.assigned_to, output))

        # Check if parent task should be updated
        self._check_parent_completion(task)

        return True

    def block_task(self, task_id: str, reason: str, critical: bool = False) -> bool:
        """Mark task as blocked."""
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        task.status = TaskStatus.BLOCKED
        task.error = reason

        self.event_bus.emit(worker_blocked(task, task.assigned_to, reason, critical))

        return True

    def fail_task(self, task_id: str, error: str) -> bool:
        """Mark task as failed."""
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        task.status = TaskStatus.FAILED
        task.completed_at = datetime.now()
        task.error = error

        self.event_bus.emit(Event(
            type=EventType.TASK_FAILED,
            task_id=task_id,
            title=f"Failed: {task.title}",
            message=error,
            source_worker_id=task.assigned_to
        ))

        return True

    def unblock_task(self, task_id: str, resolution: str) -> bool:
        """Unblock a task and resume it."""
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        if task.status != TaskStatus.BLOCKED:
            return False

        task.status = TaskStatus.IN_PROGRESS
        task.error = None

        self.event_bus.emit(Event(
            type=EventType.PROGRESS,
            task_id=task_id,
            title=f"Unblocked: {task.title}",
            message=resolution,
        ))

        return True

    def _check_parent_completion(self, task: Task) -> None:
        """Check if all subtasks of parent are complete."""
        if not task.parent_task_id:
            return

        parent = self.tasks.get(task.parent_task_id)
        if not parent:
            return

        # Check all subtasks
        all_complete = all(
            self.tasks[sid].status == TaskStatus.COMPLETED
            for sid in parent.subtask_ids
            if sid in self.tasks
        )

        if all_complete and parent.subtask_ids:
            # Summarize subtask outputs
            outputs = [
                f"- {self.tasks[sid].title}: {self.tasks[sid].output}"
                for sid in parent.subtask_ids
                if sid in self.tasks
            ]
            parent.output = "All subtasks completed:\n" + "\n".join(outputs)
            parent.status = TaskStatus.COMPLETED
            parent.completed_at = datetime.now()

            self.event_bus.emit(Event(
                type=EventType.TASK_COMPLETED,
                task_id=parent.id,
                title=f"Goal completed: {parent.title}",
                message=parent.output,
            ))

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self.tasks.get(task_id)

    def get_tasks_for_worker(self, worker_id: str) -> List[Task]:
        """Get all tasks assigned to a worker."""
        return [t for t in self.tasks.values() if t.assigned_to == worker_id]

    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """Get all tasks with a given status."""
        return [t for t in self.tasks.values() if t.status == status]

    def get_pending_tasks(self) -> List[Task]:
        """Get tasks waiting to be assigned or started."""
        return [
            t for t in self.tasks.values()
            if t.status in [TaskStatus.PENDING]
        ]

    def get_active_tasks(self) -> List[Task]:
        """Get tasks currently being worked on."""
        return [
            t for t in self.tasks.values()
            if t.status == TaskStatus.IN_PROGRESS
        ]

    def get_blocked_tasks(self) -> List[Task]:
        """Get all blocked tasks."""
        return self.get_tasks_by_status(TaskStatus.BLOCKED)
