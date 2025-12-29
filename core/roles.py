"""
Role management - load roles from config files.

Roles define personas, capabilities, and hierarchy.
Users can customize roles without touching code.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Optional
from .models import Role


DEFAULT_ROLES = {
    "engineering_manager": Role(
        id="engineering_manager",
        name="Engineering Manager",
        system_prompt="""You are an Engineering Manager in a software development organization.

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

Always be proactive about status updates.""",
        can_delegate=True,
        reports_to="ceo",
        capabilities=["create_tasks", "assign_tasks", "review_code"]
    ),

    "developer": Role(
        id="developer",
        name="Developer",
        system_prompt="""You are a Software Developer working on assigned tasks.

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
- Emit a 'blocked' event so your manager knows

If you have a question:
- Be specific about what you need to know
- Emit a 'question' event

Always update your status as you work.""",
        can_delegate=False,
        reports_to="engineering_manager",
        capabilities=["write_code", "run_tests", "read_docs"]
    ),

    "qa_engineer": Role(
        id="qa_engineer",
        name="QA Engineer",
        system_prompt="""You are a QA Engineer responsible for testing and quality.

Your responsibilities:
- Review code changes for quality
- Write and run tests
- Report bugs and issues
- Verify fixes

Be thorough but pragmatic about testing.""",
        can_delegate=False,
        reports_to="engineering_manager",
        capabilities=["run_tests", "review_code", "write_tests"]
    ),
}


class RoleManager:
    """Loads and manages role definitions."""

    def __init__(self, config_dir: Optional[Path] = None):
        self.roles: Dict[str, Role] = {}
        self.config_dir = config_dir or Path.home() / ".claude-swarm" / "roles"

        # Load default roles
        self.roles.update(DEFAULT_ROLES)

        # Load custom roles from config
        self._load_custom_roles()

    def _load_custom_roles(self):
        """Load roles from YAML files in config directory."""
        if not self.config_dir.exists():
            return

        for file in self.config_dir.glob("*.yaml"):
            try:
                with open(file) as f:
                    data = yaml.safe_load(f)
                    if data:
                        for role_id, role_data in data.items():
                            self.roles[role_id] = Role(
                                id=role_id,
                                name=role_data.get("name", role_id),
                                system_prompt=role_data.get("system_prompt", ""),
                                can_delegate=role_data.get("can_delegate", False),
                                reports_to=role_data.get("reports_to"),
                                capabilities=role_data.get("capabilities", []),
                                mcp_servers=role_data.get("mcp_servers", [])
                            )
            except Exception as e:
                print(f"Warning: Failed to load role file {file}: {e}")

    def get_role(self, role_id: str) -> Optional[Role]:
        """Get a role by ID."""
        return self.roles.get(role_id)

    def list_roles(self) -> Dict[str, Role]:
        """Get all available roles."""
        return self.roles.copy()

    def get_subordinates(self, role_id: str) -> list[Role]:
        """Get roles that report to this role."""
        return [r for r in self.roles.values() if r.reports_to == role_id]

    def get_supervisor(self, role_id: str) -> Optional[Role]:
        """Get the role this role reports to."""
        role = self.roles.get(role_id)
        if role and role.reports_to:
            return self.roles.get(role.reports_to)
        return None


def create_example_config(config_dir: Path):
    """Create example role config file for users to customize."""
    config_dir.mkdir(parents=True, exist_ok=True)

    example = """# Custom role definitions
# Add your own roles or override defaults

# Example: Custom frontend developer role
frontend_dev:
  name: "Frontend Developer"
  system_prompt: |
    You are a Frontend Developer specializing in React and TypeScript.
    Focus on UI/UX, component design, and user experience.
  can_delegate: false
  reports_to: engineering_manager
  capabilities:
    - write_code
    - run_tests
    - review_ui

# Example: DevOps engineer
devops:
  name: "DevOps Engineer"
  system_prompt: |
    You are a DevOps Engineer managing infrastructure and deployments.
    Focus on CI/CD, monitoring, and reliability.
  can_delegate: false
  reports_to: engineering_manager
  capabilities:
    - manage_infrastructure
    - deploy
    - monitor
  mcp_servers:
    - docker
    - kubernetes
"""

    example_file = config_dir / "custom_roles.yaml.example"
    if not example_file.exists():
        with open(example_file, 'w') as f:
            f.write(example)
