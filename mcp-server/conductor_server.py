#!/usr/bin/env python3
"""
Claude Conductor MCP Server

Provides tools for a conductor Claude to orchestrate worker Claude sessions.
Communicates with the Claude Conductor app via HTTP API on port 7422.
"""

import json
import urllib.request
import urllib.error
from typing import Optional
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("claude-conductor")

# HTTP API base URL (Claude Conductor app)
API_BASE = "http://127.0.0.1:7422"


def api_request(method: str, path: str, body: dict = None) -> dict:
    """Make an HTTP request to the Claude Conductor app API"""
    url = f"{API_BASE}{path}"

    data = None
    if body:
        data = json.dumps(body).encode('utf-8')

    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={'Content-Type': 'application/json'} if data else {}
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.URLError as e:
        return {"error": f"Failed to connect to Claude Conductor app: {e}"}
    except json.JSONDecodeError:
        return {"error": "Invalid response from Claude Conductor app"}


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes and terminal control sequences for cleaner output"""
    import re

    # Remove all ANSI escape sequences
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    text = ansi_escape.sub('', text)

    # Remove other escape sequences (OSC, etc)
    text = re.sub(r'\x1B\][^\x07]*\x07', '', text)  # OSC sequences
    text = re.sub(r'\x1B[PX^_][^\x1B]*\x1B\\', '', text)  # DCS, SOS, PM, APC

    # Remove control characters except newline and tab
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)

    # Handle carriage returns (spinner overwrites) - keep only final content per line
    lines = []
    for line in text.split('\n'):
        if '\r' in line:
            # Keep only content after last carriage return
            parts = line.split('\r')
            line = parts[-1] if parts[-1].strip() else (parts[-2] if len(parts) > 1 else '')
        lines.append(line)
    text = '\n'.join(lines)

    # Remove excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def extract_claude_response(text: str) -> str:
    """Extract the actual Claude response content from terminal output"""
    import re

    text = strip_ansi(text)

    # Remove Claude Code UI elements
    patterns_to_remove = [
        r'^\s*\*\s+Claude Code.*$',  # Claude Code header
        r'^\s*\*\s+Opus.*$',  # Model info
        r'^\s*\*\s+~/.*$',  # Directory path
        r'^A gift for you.*$',  # Gift message
        r'^Your rate limits.*$',  # Rate limit message
        r'^\s*>\s*$',  # Empty prompt
        r'^\s*\? for shortcuts\s*$',  # Shortcuts hint
        r'^\s*[●·✢✳✶✻✽]\s*(Thinking|Imagining|Noodling|Pondering).*$',  # All spinner variants
        r'^\s*⎿.*$',  # Tool output markers
        r'^\s*\.\.\.\s*$',  # Ellipsis
        r'^─+$',  # Horizontal lines
    ]

    lines = text.split('\n')
    filtered_lines = []

    for line in lines:
        skip = False
        for pattern in patterns_to_remove:
            if re.match(pattern, line, re.IGNORECASE | re.MULTILINE):
                skip = True
                break
        if not skip:
            filtered_lines.append(line)

    # Remove excessive blank lines from result
    result = '\n'.join(filtered_lines)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()


@mcp.tool()
def create_worker(name: str, directory: str, mcp_port: int = 55558) -> dict:
    """
    Create a new worker Claude session that appears in the Conductor UI.

    Args:
        name: Name for the worker (e.g., "combat-worker", "ui-worker")
        directory: Working directory for the worker
        mcp_port: MCP port for the worker (default 55558)

    Returns:
        Dict with worker ID and status
    """
    result = api_request("POST", "/sessions", {
        "name": name,
        "directory": directory,
        "mcp_port": mcp_port,
        "role": "Worker"
    })

    return result


@mcp.tool()
def send_to_worker(worker_id: str, message: str) -> dict:
    """
    Send a message/prompt to a specific worker.

    Args:
        worker_id: The UUID of the worker to send to
        message: The message or prompt to send

    Returns:
        Dict with status
    """
    result = api_request("POST", f"/sessions/{worker_id}/send", {
        "message": message
    })

    return result


@mcp.tool()
def broadcast_to_workers(message: str) -> dict:
    """
    Send a message to ALL workers.

    Args:
        message: The message or prompt to send to all workers

    Returns:
        Dict with results for each worker
    """
    # First get all sessions
    sessions_result = api_request("GET", "/sessions")

    if "error" in sessions_result:
        return sessions_result

    results = {}
    workers = [s for s in sessions_result.get("sessions", []) if s.get("role") == "Worker"]

    for worker in workers:
        worker_id = worker["id"]
        result = send_to_worker(worker_id, message)
        results[worker_id] = result

    return {
        "broadcast_message": message,
        "results": results,
        "workers_count": len(results)
    }


@mcp.tool()
def get_worker_output(worker_id: str) -> dict:
    """
    Get recent output from a worker.

    Args:
        worker_id: The UUID of the worker

    Returns:
        Dict with worker output
    """
    result = api_request("GET", f"/sessions/{worker_id}/output")

    if "output" in result:
        result["output"] = extract_claude_response(result["output"])

    return result


@mcp.tool()
def list_workers() -> dict:
    """
    List all sessions (conductor and workers) and their status.

    Returns:
        Dict with all sessions and their info
    """
    result = api_request("GET", "/sessions")
    return result


@mcp.tool()
def terminate_worker(worker_id: str) -> dict:
    """
    Terminate/remove a worker session.

    Args:
        worker_id: The UUID of the worker to terminate

    Returns:
        Dict with termination status
    """
    result = api_request("DELETE", f"/sessions/{worker_id}")
    return result


@mcp.tool()
def get_all_outputs() -> dict:
    """
    Get recent output from ALL workers at once.
    Useful for checking on everyone's progress.

    Returns:
        Dict with output from all workers
    """
    # First get all sessions
    sessions_result = api_request("GET", "/sessions")

    if "error" in sessions_result:
        return sessions_result

    all_outputs = {}
    workers = [s for s in sessions_result.get("sessions", []) if s.get("role") == "Worker"]

    for worker in workers:
        worker_id = worker["id"]
        output_result = get_worker_output(worker_id)
        all_outputs[worker["name"]] = {
            "id": worker_id,
            "status": worker.get("status", "Unknown"),
            "output": output_result.get("output", "")[:2000]  # Limit output size
        }

    return {
        "outputs": all_outputs,
        "count": len(all_outputs)
    }


@mcp.tool()
def wait_for_workers(timeout_seconds: int = 120) -> dict:
    """
    Wait for all workers to complete their tasks and return their outputs.

    A worker is considered "done" when its output contains the Claude Code prompt
    indicator ("> " at the start of a line after their task output).

    Args:
        timeout_seconds: Maximum time to wait (default 120 seconds)

    Returns:
        Dict with all worker outputs once they're done
    """
    import time

    start_time = time.time()
    check_interval = 3  # Check every 3 seconds

    while time.time() - start_time < timeout_seconds:
        sessions_result = api_request("GET", "/sessions")

        if "error" in sessions_result:
            return sessions_result

        workers = [s for s in sessions_result.get("sessions", []) if s.get("role") == "Worker"]

        if not workers:
            return {"error": "No workers found"}

        all_done = True
        outputs = {}

        for worker in workers:
            worker_id = worker["id"]
            output_result = api_request("GET", f"/sessions/{worker_id}/output")
            output = output_result.get("output", "")

            # Check if worker is done (prompt is showing - line starts with "> ")
            lines = output.strip().split('\n')
            is_done = False
            if lines:
                last_lines = lines[-5:]  # Check last 5 lines
                for line in last_lines:
                    clean_line = strip_ansi(line).strip()
                    if clean_line.startswith("> ") or clean_line == ">" or "? for shortcuts" in clean_line:
                        is_done = True
                        break

            outputs[worker["name"]] = {
                "id": worker_id,
                "done": is_done,
                "output": extract_claude_response(output)[-3000:]  # Last 3000 chars, cleaned
            }

            if not is_done:
                all_done = False

        if all_done:
            return {
                "status": "all_complete",
                "outputs": outputs,
                "elapsed_seconds": int(time.time() - start_time)
            }

        time.sleep(check_interval)

    # Timeout - return partial results
    return {
        "status": "timeout",
        "outputs": outputs,
        "elapsed_seconds": timeout_seconds,
        "message": "Some workers did not complete in time"
    }


# =============================================================================
# Multi-UE Instance Management Tools
# =============================================================================

@mcp.tool()
def list_worktrees(project_dir: str) -> dict:
    """
    List all git worktrees for a project.

    Args:
        project_dir: Path to the main git repository

    Returns:
        Dict with list of worktrees and their branches
    """
    import subprocess

    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return {"error": f"Git command failed: {result.stderr}"}

        worktrees = []
        current = {}
        for line in result.stdout.strip().split('\n'):
            if line.startswith('worktree '):
                if current:
                    worktrees.append(current)
                current = {"path": line[9:]}
            elif line.startswith('HEAD '):
                current["head"] = line[5:]
            elif line.startswith('branch '):
                current["branch"] = line[7:].replace('refs/heads/', '')
            elif line == 'bare':
                current["bare"] = True
            elif line == 'detached':
                current["detached"] = True

        if current:
            worktrees.append(current)

        return {"worktrees": worktrees, "count": len(worktrees)}

    except subprocess.TimeoutExpired:
        return {"error": "Git command timed out"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def create_worktree(project_dir: str, worktree_path: str, branch_name: str) -> dict:
    """
    Create a new git worktree for parallel development.

    Args:
        project_dir: Path to the main git repository
        worktree_path: Path where the new worktree should be created
        branch_name: Name of the branch to create/checkout

    Returns:
        Dict with worktree creation status
    """
    import subprocess
    import os

    try:
        # Check if worktree already exists
        if os.path.exists(worktree_path):
            return {"error": f"Path already exists: {worktree_path}"}

        # Create worktree with new branch
        result = subprocess.run(
            ["git", "worktree", "add", worktree_path, "-b", branch_name],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            # Try without -b if branch already exists
            result = subprocess.run(
                ["git", "worktree", "add", worktree_path, branch_name],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=60
            )

        if result.returncode != 0:
            return {"error": f"Failed to create worktree: {result.stderr}"}

        return {
            "status": "created",
            "path": worktree_path,
            "branch": branch_name,
            "message": result.stdout.strip()
        }

    except subprocess.TimeoutExpired:
        return {"error": "Git command timed out"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def remove_worktree(project_dir: str, worktree_path: str, force: bool = False) -> dict:
    """
    Remove a git worktree.

    Args:
        project_dir: Path to the main git repository
        worktree_path: Path of the worktree to remove
        force: Force removal even if worktree is dirty

    Returns:
        Dict with removal status
    """
    import subprocess

    try:
        cmd = ["git", "worktree", "remove", worktree_path]
        if force:
            cmd.append("--force")

        result = subprocess.run(
            cmd,
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return {"error": f"Failed to remove worktree: {result.stderr}"}

        return {"status": "removed", "path": worktree_path}

    except subprocess.TimeoutExpired:
        return {"error": "Git command timed out"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def configure_ue_mcp_port(project_dir: str, port: int) -> dict:
    """
    Configure the MCP server port for an Unreal Engine project.
    This modifies Config/DefaultGame.ini to set [UnrealMCP] ServerPort.

    Args:
        project_dir: Path to the UE project directory
        port: Port number for the MCP server (e.g., 55557, 55558)

    Returns:
        Dict with configuration status
    """
    import os

    config_path = os.path.join(project_dir, "Config", "DefaultGame.ini")

    try:
        # Read existing config if it exists
        content = ""
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                content = f.read()

        # Check if [UnrealMCP] section exists
        if "[UnrealMCP]" in content:
            # Update existing section
            import re
            if "ServerPort=" in content:
                content = re.sub(
                    r'(\[UnrealMCP\][^\[]*ServerPort=)\d+',
                    f'\\g<1>{port}',
                    content
                )
            else:
                content = content.replace(
                    "[UnrealMCP]",
                    f"[UnrealMCP]\nServerPort={port}"
                )
        else:
            # Add new section
            content += f"\n\n[UnrealMCP]\nServerPort={port}\n"

        # Ensure Config directory exists
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        with open(config_path, 'w') as f:
            f.write(content)

        return {
            "status": "configured",
            "config_file": config_path,
            "port": port
        }

    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def launch_ue_editor(project_path: str) -> dict:
    """
    Launch Unreal Editor for a project (macOS).

    Args:
        project_path: Path to the .uproject file or project directory

    Returns:
        Dict with launch status
    """
    import subprocess
    import os

    try:
        # Find .uproject file
        if project_path.endswith('.uproject'):
            uproject = project_path
        else:
            # Look for .uproject file in directory
            for f in os.listdir(project_path):
                if f.endswith('.uproject'):
                    uproject = os.path.join(project_path, f)
                    break
            else:
                return {"error": f"No .uproject file found in {project_path}"}

        if not os.path.exists(uproject):
            return {"error": f"Project file not found: {uproject}"}

        # Launch with 'open' on macOS (non-blocking)
        subprocess.Popen(
            ["open", uproject],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        return {
            "status": "launched",
            "project": uproject,
            "message": "Unreal Editor is starting..."
        }

    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def check_ue_mcp_connection(port: int = 55557) -> dict:
    """
    Check if an Unreal Editor instance is running and MCP is accessible.

    Args:
        port: MCP port to check (default 55557)

    Returns:
        Dict with connection status
    """
    import socket

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()

        if result == 0:
            return {"status": "connected", "port": port, "message": "UE MCP is running"}
        else:
            return {"status": "not_connected", "port": port, "message": "UE MCP not responding"}

    except Exception as e:
        return {"status": "error", "port": port, "error": str(e)}


@mcp.tool()
def setup_multi_ue_workspace(
    main_project_dir: str,
    num_instances: int = 2,
    base_port: int = 55557
) -> dict:
    """
    Set up a complete multi-UE workspace with worktrees and port configuration.

    This creates worktrees and configures each for a different MCP port.
    The main project uses base_port, worktree-2 uses base_port+1, etc.

    Args:
        main_project_dir: Path to the main UE project (must be a git repo)
        num_instances: Number of UE instances to set up (default 2)
        base_port: Starting port number (default 55557)

    Returns:
        Dict with setup results for each instance
    """
    import os

    results = {
        "instances": [],
        "status": "success"
    }

    # Instance 1 is the main project
    main_result = configure_ue_mcp_port(main_project_dir, base_port)
    results["instances"].append({
        "name": "main",
        "path": main_project_dir,
        "port": base_port,
        "config_result": main_result
    })

    # Create worktrees for additional instances
    parent_dir = os.path.dirname(main_project_dir)
    project_name = os.path.basename(main_project_dir)

    for i in range(2, num_instances + 1):
        port = base_port + (i - 1)
        worktree_name = f"{project_name}-wt{i}"
        worktree_path = os.path.join(parent_dir, worktree_name)
        branch_name = f"parallel-{i}"

        instance_result = {
            "name": worktree_name,
            "path": worktree_path,
            "port": port,
            "branch": branch_name
        }

        # Create worktree if it doesn't exist
        if not os.path.exists(worktree_path):
            wt_result = create_worktree(main_project_dir, worktree_path, branch_name)
            instance_result["worktree_result"] = wt_result
            if "error" in wt_result:
                results["status"] = "partial"
                results["instances"].append(instance_result)
                continue

        # Configure MCP port
        config_result = configure_ue_mcp_port(worktree_path, port)
        instance_result["config_result"] = config_result

        results["instances"].append(instance_result)

    return results


if __name__ == "__main__":
    mcp.run()
