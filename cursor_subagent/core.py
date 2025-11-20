#!/usr/bin/env python3
"""
Core functionality for cursor-subagent - shared between CLI and MCP server.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


# Default dylib location
DEFAULT_DYLIB_DIR = Path.home() / ".local" / "share" / "cursor-subagent"
DEFAULT_DYLIB_PATH = DEFAULT_DYLIB_DIR / "libcursor_redirect.dylib"


def get_dylib_path() -> Path:
    """Get the path to the dylib."""
    # Check environment override
    if env_path := os.environ.get("CURSOR_SUBAGENT_DYLIB_PATH"):
        return Path(env_path)

    # Check default location
    if DEFAULT_DYLIB_PATH.exists():
        return DEFAULT_DYLIB_PATH

    # Check local directory (for development)
    local_dylib = Path.cwd() / "libcursor_redirect.dylib"
    if local_dylib.exists():
        return local_dylib

    # Check in package directory (for installed package)
    package_dylib = Path(__file__).parent / "libcursor_redirect.dylib"
    if package_dylib.exists():
        return package_dylib

    # Default to standard location
    return DEFAULT_DYLIB_PATH


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path.cwd()


def get_agents_dir() -> Path:
    """Get the agents directory."""
    return get_project_root() / ".cursor" / "agents"


def get_cursor_agent_path() -> Path:
    """Get the path to cursor-agent executable."""
    return Path.home() / ".local" / "bin" / "cursor-agent"


def list_agents() -> list[str]:
    """List all available agents."""
    agents_dir = get_agents_dir()
    if not agents_dir.exists():
        return []

    return [
        d.name for d in agents_dir.iterdir()
        if d.is_dir() and (d / ".cursorrules").exists()
    ]


def get_agent_info(name: str) -> Optional[dict]:
    """Get information about a specific agent."""
    agent_path = get_agents_dir() / name
    if not agent_path.exists():
        return None

    info = {
        "name": name,
        "path": str(agent_path),
        "has_rules": (agent_path / ".cursorrules").exists() or ((agent_path / "rules").is_dir() and len(list((agent_path / "rules").iterdir())) > 0),
        "has_mcp_config": (agent_path / "mcp.json").exists(),
    }

    # Read description if available
    desc_file = agent_path / "description.txt"
    if desc_file.exists():
        info["description"] = desc_file.read_text().strip()

    return info


def run_with_agent(
    agent_name: str,
    cursor_agent_args: list[str],
    workspace_path: Optional[str] = None
) -> int:
    """
    Run cursor-agent with agent configuration injected via dylib.

    Args:
        agent_name: Agent name
        cursor_agent_args: Arguments to pass to cursor-agent
        workspace_path: Optional workspace path

    Returns:
        Exit code from cursor-agent
    """
    agent_path = get_agents_dir() / agent_name
    if not agent_path.exists():
        print(f"Error: Agent '{agent_name}' does not exist", file=sys.stderr)
        print(f"Available agents: {', '.join(list_agents())}", file=sys.stderr)
        return 1

    # Determine workspace path
    if workspace_path is None:
        workspace_path = str(get_project_root())

    # Get dylib path
    dylib_path = get_dylib_path()
    if not dylib_path.exists():
        print(f"Error: Dylib not found at {dylib_path}", file=sys.stderr)
        print("Please check your installation method against the README", file=sys.stderr)
        return 1

    # Set up environment for dylib redirection
    env = os.environ.copy()
    env["DYLD_INSERT_LIBRARIES"] = str(dylib_path)
    env["CURSOR_REDIRECT_TARGET"] = str(agent_path)
    env["CURSOR_REDIRECT_SOURCE"] = str(get_project_root() / ".cursor")

    # Get cursor-agent path
    cursor_agent = get_cursor_agent_path()
    if not cursor_agent.exists():
        print(f"Error: cursor-agent not found at {cursor_agent}", file=sys.stderr)
        return 1

    # Build command
    cmd = [str(cursor_agent)] + cursor_agent_args

    # Execute cursor-agent with the agent configuration
    try:
        result = subprocess.run(
            cmd,
            env=env,
            cwd=workspace_path
        )
        return result.returncode
    except Exception as e:
        print(f"Error executing cursor-agent: {e}", file=sys.stderr)
        return 1
