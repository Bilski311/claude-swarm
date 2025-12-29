#!/usr/bin/env python3
"""
Claude Swarm MCP Server

Provides tools for orchestrating a multi-agent organization.
CEO (user) interacts through these tools to manage the swarm.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Optional, List
from mcp.server.fastmcp import FastMCP

from core.swarm import Swarm
from core.models import TaskStatus

# Initialize
mcp = FastMCP("claude-swarm")
swarm = Swarm(name="Engineering Team")


# =============================================================================
# Organization Management
# =============================================================================

@mcp.tool()
def get_org_status() -> dict:
    """
    Get the current status of your organization.

    Shows:
    - All workers and their current status
    - Task counts (active, blocked, pending)
    - Pending notifications that need your attention

    Returns:
        Organization status summary
    """
    return swarm.get_status()


@mcp.tool()
def get_notifications() -> dict:
    """
    Get notifications that need CEO attention.

    These include:
    - Workers who are blocked and need help
    - Questions from workers
    - Escalations from managers

    Returns:
        List of pending notifications
    """
    notifications = swarm.get_notifications()
    return {
        "notifications": notifications,
        "count": len(notifications)
    }


@mcp.tool()
def respond_to_notification(notification_id: str, response: str) -> dict:
    """
    Respond to a notification (question, blocker, escalation).

    Args:
        notification_id: ID of the notification to respond to
        response: Your response or decision

    Returns:
        Status of the response
    """
    success = swarm.respond_to_event(notification_id, response)
    return {"status": "sent" if success else "failed"}


# =============================================================================
# Worker Management
# =============================================================================

@mcp.tool()
def hire_worker(
    role: str,
    name: str,
    directory: str,
    mcp_port: int = None
) -> dict:
    """
    Hire a new worker with a specific role.

    Available roles:
    - engineering_manager: Breaks down goals, manages developers
    - developer: Writes code, completes tasks
    - qa_engineer: Tests and reviews code

    Args:
        role: Role ID (engineering_manager, developer, qa_engineer)
        name: Name for this worker
        directory: Working directory for the worker
        mcp_port: Optional MCP port for multi-instance setups

    Returns:
        Worker details
    """
    worker = swarm.hire_worker(role, name, directory, mcp_port)
    if worker:
        return {
            "status": "hired",
            "worker_id": worker.id,
            "name": worker.name,
            "role": worker.role_id
        }
    return {"status": "failed", "error": "Could not create worker"}


@mcp.tool()
def fire_worker(worker_id: str) -> dict:
    """
    Remove a worker from the organization.

    Args:
        worker_id: ID of the worker to remove

    Returns:
        Status of the removal
    """
    success = swarm.fire_worker(worker_id)
    return {"status": "removed" if success else "not_found"}


@mcp.tool()
def list_workers() -> dict:
    """
    List all workers in the organization.

    Returns:
        List of workers with their roles and status
    """
    return {
        "workers": [
            {
                "id": w.id,
                "name": w.name,
                "role": w.role_id,
                "status": w.status,
                "current_task": w.current_task_id
            }
            for w in swarm.workers.values()
        ],
        "count": len(swarm.workers)
    }


@mcp.tool()
def list_available_roles() -> dict:
    """
    List all available roles that can be assigned to workers.

    Returns:
        List of roles with descriptions
    """
    roles = swarm.role_manager.list_roles()
    return {
        "roles": [
            {
                "id": r.id,
                "name": r.name,
                "can_delegate": r.can_delegate,
                "reports_to": r.reports_to,
                "capabilities": r.capabilities
            }
            for r in roles.values()
        ]
    }


# =============================================================================
# Task & Goal Management
# =============================================================================

@mcp.tool()
def submit_goal(goal: str, description: str = "") -> dict:
    """
    Submit a high-level goal for the engineering team.

    The goal will be sent to the Engineering Manager who will:
    1. Break it down into specific tasks
    2. Assign tasks to developers
    3. Report back on progress

    Args:
        goal: Short title of the goal
        description: Detailed description of what you want

    Returns:
        Task details
    """
    task = swarm.submit_goal(goal, description)
    return {
        "status": "submitted",
        "task_id": task.id,
        "title": task.title,
        "assigned_role": task.assigned_role
    }


@mcp.tool()
def get_tasks(status: str = None) -> dict:
    """
    Get tasks in the organization.

    Args:
        status: Filter by status (pending, in_progress, blocked, completed, failed)
                Leave empty for all tasks.

    Returns:
        List of tasks
    """
    if status:
        try:
            task_status = TaskStatus(status)
            tasks = swarm.task_manager.get_tasks_by_status(task_status)
        except ValueError:
            return {"error": f"Invalid status: {status}"}
    else:
        tasks = list(swarm.task_manager.tasks.values())

    return {
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "status": t.status.value,
                "assigned_to": t.assigned_to,
                "output": t.output[:500] if t.output else None
            }
            for t in tasks
        ],
        "count": len(tasks)
    }


@mcp.tool()
def get_blocked_tasks() -> dict:
    """
    Get all tasks that are currently blocked.

    Returns:
        List of blocked tasks with reasons
    """
    tasks = swarm.task_manager.get_blocked_tasks()
    return {
        "blocked_tasks": [
            {
                "id": t.id,
                "title": t.title,
                "assigned_to": t.assigned_to,
                "reason": t.error
            }
            for t in tasks
        ],
        "count": len(tasks)
    }


@mcp.tool()
def unblock_task(task_id: str, resolution: str) -> dict:
    """
    Unblock a task by providing resolution.

    Args:
        task_id: ID of the blocked task
        resolution: How to proceed / answer to the blocker

    Returns:
        Status
    """
    success = swarm.task_manager.unblock_task(task_id, resolution)
    if success:
        # Notify the worker
        task = swarm.task_manager.get_task(task_id)
        if task and task.assigned_to:
            swarm._send_to_worker(task.assigned_to, f"""Your task has been unblocked:

Resolution: {resolution}

Please continue with: {task.title}""")
    return {"status": "unblocked" if success else "failed"}


# =============================================================================
# Direct Communication
# =============================================================================

@mcp.tool()
def message_worker(worker_id: str, message: str) -> dict:
    """
    Send a direct message to a specific worker.

    Args:
        worker_id: ID of the worker
        message: Your message

    Returns:
        Status
    """
    success = swarm._send_to_worker(worker_id, message)
    return {"status": "sent" if success else "failed"}


@mcp.tool()
def broadcast_message(message: str, role: str = None) -> dict:
    """
    Broadcast a message to all workers (or workers with a specific role).

    Args:
        message: Your message
        role: Optional role filter (only message workers with this role)

    Returns:
        Status
    """
    workers = swarm.workers.values()
    if role:
        workers = [w for w in workers if w.role_id == role]

    sent = 0
    for worker in workers:
        if swarm._send_to_worker(worker.id, message):
            sent += 1

    return {"status": "sent", "recipients": sent}


@mcp.tool()
def get_worker_output(worker_id: str) -> dict:
    """
    Get the current output from a worker's terminal.

    Args:
        worker_id: ID of the worker

    Returns:
        Worker output
    """
    import urllib.request
    import json

    try:
        with urllib.request.urlopen(
            f"{swarm._conductor_api_url}/sessions/{worker_id}/output",
            timeout=10
        ) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            # Clean up the output
            output = data.get("output", "")
            # Basic ANSI stripping
            import re
            output = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', output)
            return {
                "worker_id": worker_id,
                "output": output[-3000:]  # Last 3000 chars
            }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    mcp.run()
