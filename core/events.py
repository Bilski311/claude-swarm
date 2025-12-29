"""
Event system for async communication.

Events flow up the hierarchy until handled.
CEO gets notified of things that need attention.
"""

from datetime import datetime
from typing import Callable, Dict, List, Optional
from dataclasses import dataclass, field
from .models import Event, EventType, Task, TaskStatus


# Event handlers registry
_handlers: Dict[EventType, List[Callable]] = {}


def on_event(event_type: EventType):
    """Decorator to register event handlers."""
    def decorator(func: Callable):
        if event_type not in _handlers:
            _handlers[event_type] = []
        _handlers[event_type].append(func)
        return func
    return decorator


def emit(event: Event):
    """Emit an event to all registered handlers."""
    handlers = _handlers.get(event.type, [])
    for handler in handlers:
        try:
            handler(event)
        except Exception as e:
            print(f"Event handler error: {e}")


class EventBus:
    """
    Central event bus for the organization.
    Routes events to appropriate handlers and tracks history.
    """

    def __init__(self):
        self.events: List[Event] = []
        self.pending_for_ceo: List[Event] = []  # Events CEO needs to see
        self.handlers: Dict[str, List[Callable]] = {}  # role_id -> handlers

    def emit(self, event: Event) -> None:
        """
        Emit an event. Routes based on type and source.
        """
        event.created_at = datetime.now()
        self.events.append(event)

        # Determine who should handle this
        if event.type in [EventType.ESCALATION, EventType.BLOCKED, EventType.QUESTION]:
            # These might need CEO attention
            if event.requires_response or self._should_escalate_to_ceo(event):
                self.pending_for_ceo.append(event)

        # Notify registered handlers
        if event.target_role_id and event.target_role_id in self.handlers:
            for handler in self.handlers[event.target_role_id]:
                try:
                    handler(event)
                except Exception as e:
                    print(f"Handler error for {event.target_role_id}: {e}")

        # Also trigger global handlers
        emit(event)

    def _should_escalate_to_ceo(self, event: Event) -> bool:
        """Determine if event needs CEO attention."""
        # Escalations always go to CEO
        if event.type == EventType.ESCALATION:
            return True

        # Questions that couldn't be answered by manager
        if event.type == EventType.QUESTION and event.data.get("escalated"):
            return True

        # Blockers that have been pending too long
        if event.type == EventType.BLOCKED:
            # Could add time-based logic here
            return event.data.get("critical", False)

        return False

    def register_handler(self, role_id: str, handler: Callable) -> None:
        """Register a handler for events targeting a role."""
        if role_id not in self.handlers:
            self.handlers[role_id] = []
        self.handlers[role_id].append(handler)

    def get_pending_for_ceo(self) -> List[Event]:
        """Get events that need CEO attention."""
        return [e for e in self.pending_for_ceo if not e.handled]

    def get_events_for_task(self, task_id: str) -> List[Event]:
        """Get all events related to a task."""
        return [e for e in self.events if e.task_id == task_id]

    def get_recent_events(self, limit: int = 50) -> List[Event]:
        """Get recent events, newest first."""
        return sorted(self.events, key=lambda e: e.created_at, reverse=True)[:limit]

    def mark_handled(self, event_id: str, handler_id: str, response: Optional[str] = None) -> None:
        """Mark an event as handled."""
        for event in self.events:
            if event.id == event_id:
                event.handled = True
                event.handled_by = handler_id
                event.response = response
                break

        # Remove from pending if it was there
        self.pending_for_ceo = [e for e in self.pending_for_ceo if e.id != event_id]


# Helper functions for common event patterns

def task_completed(task: Task, worker_id: str, output: str) -> Event:
    """Create a task completed event."""
    return Event(
        type=EventType.TASK_COMPLETED,
        source_worker_id=worker_id,
        task_id=task.id,
        title=f"Completed: {task.title}",
        message=output,
        data={"task_title": task.title, "duration": str(datetime.now() - task.started_at) if task.started_at else None}
    )


def worker_blocked(task: Task, worker_id: str, reason: str, critical: bool = False) -> Event:
    """Create a blocked event."""
    return Event(
        type=EventType.BLOCKED,
        source_worker_id=worker_id,
        task_id=task.id,
        title=f"Blocked: {task.title}",
        message=reason,
        requires_response=True,
        data={"critical": critical, "task_title": task.title}
    )


def worker_question(task: Task, worker_id: str, question: str) -> Event:
    """Create a question event."""
    return Event(
        type=EventType.QUESTION,
        source_worker_id=worker_id,
        task_id=task.id,
        title=f"Question about: {task.title}",
        message=question,
        requires_response=True,
        data={"task_title": task.title}
    )


def escalate_to_ceo(source_role_id: str, task_id: Optional[str], reason: str) -> Event:
    """Create an escalation event for CEO."""
    return Event(
        type=EventType.ESCALATION,
        source_role_id=source_role_id,
        task_id=task_id,
        title="Needs CEO Decision",
        message=reason,
        target_role_id="ceo",
        requires_response=True,
        data={"escalated_from": source_role_id}
    )
