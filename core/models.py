"""
Core data models for Claude Swarm.

Designed for flexibility - roles, tasks, and events are the primitives
that can compose into any organizational structure.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
import uuid


class TaskStatus(Enum):
    PENDING = "pending"          # Created but not started
    IN_PROGRESS = "in_progress"  # Being worked on
    BLOCKED = "blocked"          # Worker needs help
    COMPLETED = "completed"      # Done
    FAILED = "failed"            # Could not complete


class EventType(Enum):
    # Task lifecycle
    TASK_CREATED = "task_created"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"

    # Worker needs attention
    BLOCKED = "blocked"          # Stuck, needs help
    QUESTION = "question"        # Has a question
    ESCALATION = "escalation"    # Needs higher authority

    # Progress updates
    PROGRESS = "progress"        # Status update
    DELEGATION = "delegation"    # Manager assigned task


@dataclass
class Role:
    """
    A role defines a persona and capabilities.
    Roles are loaded from config, not hardcoded.
    """
    id: str
    name: str                    # "Engineering Manager", "Backend Dev"
    system_prompt: str           # The persona/instructions
    can_delegate: bool = False   # Can this role assign tasks to others?
    reports_to: Optional[str] = None  # Role ID of supervisor
    capabilities: List[str] = field(default_factory=list)  # What can they do?

    # MCP configuration for this role's workers
    mcp_servers: List[str] = field(default_factory=list)  # Which MCP servers to enable


@dataclass
class Task:
    """
    A unit of work that can be assigned and tracked.
    Tasks can have subtasks (for delegation).
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING

    # Assignment
    assigned_to: Optional[str] = None      # Worker session ID
    assigned_role: Optional[str] = None    # Role ID
    created_by: Optional[str] = None       # Who created this task

    # Hierarchy
    parent_task_id: Optional[str] = None   # If this is a subtask
    subtask_ids: List[str] = field(default_factory=list)

    # Tracking
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Results
    output: Optional[str] = None           # Task result/deliverable
    error: Optional[str] = None            # If failed, why

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Event:
    """
    Something that happened that others might care about.
    Events flow up the hierarchy until handled.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: EventType = EventType.PROGRESS

    # Source
    source_worker_id: Optional[str] = None
    source_role_id: Optional[str] = None
    task_id: Optional[str] = None

    # Content
    title: str = ""
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    # Routing
    target_role_id: Optional[str] = None   # Who should see this?
    requires_response: bool = False         # Does this need a reply?

    # Tracking
    created_at: datetime = field(default_factory=datetime.now)
    handled: bool = False
    handled_by: Optional[str] = None
    response: Optional[str] = None


@dataclass
class Worker:
    """
    A Claude session with an assigned role.
    """
    id: str                               # Session ID from Electron app
    role_id: str                          # Which role is this worker playing
    name: str                             # Display name
    status: str = "idle"                  # idle, working, blocked, offline
    current_task_id: Optional[str] = None
    directory: Optional[str] = None       # Working directory
    mcp_port: Optional[int] = None        # For multi-instance setups


@dataclass
class Organization:
    """
    The complete org structure - roles, workers, tasks, events.
    This is the state that persists across sessions.
    """
    roles: Dict[str, Role] = field(default_factory=dict)
    workers: Dict[str, Worker] = field(default_factory=dict)
    tasks: Dict[str, Task] = field(default_factory=dict)
    events: List[Event] = field(default_factory=list)

    # Config
    name: str = "My Organization"
    ceo_notifications: List[str] = field(default_factory=list)  # Event IDs for CEO
