"""
Claude Swarm Core

The foundation for multi-agent orchestration.
"""

from .models import (
    Role,
    Task,
    TaskStatus,
    Event,
    EventType,
    Worker,
    Organization,
)
from .roles import RoleManager, DEFAULT_ROLES
from .events import EventBus, task_completed, worker_blocked, worker_question, escalate_to_ceo
from .tasks import TaskManager

__all__ = [
    # Models
    "Role",
    "Task",
    "TaskStatus",
    "Event",
    "EventType",
    "Worker",
    "Organization",
    # Managers
    "RoleManager",
    "TaskManager",
    "EventBus",
    # Helpers
    "DEFAULT_ROLES",
    "task_completed",
    "worker_blocked",
    "worker_question",
    "escalate_to_ceo",
]
