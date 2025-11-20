#!/usr/bin/env python3
"""
cursor-subagent CLI - Transparent wrapper for cursor-agent with isolated agent configurations.
"""

import sys
import subprocess
import argparse

from . import __version__
from .server import run_mcp_server
from .core import (
    list_agents,
    get_agent_info,
    run_with_agent,
    get_cursor_agent_path,
    get_dylib_path
)


def get_cursor_agent_help() -> str:
    """Get the original cursor-agent help output."""
    cursor_agent = get_cursor_agent_path()
    if not cursor_agent.exists():
        return ""

    try:
        result = subprocess.run(
            [str(cursor_agent), "--help"],
            capture_output=True,
            text=True,
            check=False
        )
        return result.stdout
    except Exception:
        return ""


def inject_cursor_subagent_help(original_help: str) -> str:
    """
    Inject cursor-subagent options and commands into the original help.
    """
    if not original_help:
        return "cursor-agent not found. Install Cursor to use cursor-subagent."

    lines = original_help.split('\n')
    output = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Prepend -a/--agent option *before* --resume
        if '--resume' in line:
            output.append('  -a, --agent <name>           Use a specific agent configuration')
            output.append(line)
            i += 1
            continue

        # Prepend list-agents before the help command
        if line.strip().startswith('help '):
            output.append('  list-agents                  List all available subagent configurations')
            output.append(line)
            i += 1
            continue

        output.append(line)
        i += 1


    return '\n'.join(output)


def cmd_list_agents():
    """List available agents."""
    agents = list_agents()

    if not agents:
        print("No agents found.")
        from .core import get_agents_dir
        print(f"Agents directory: {get_agents_dir()}")
        print("\nCreate agents in .cursor/agents/ with a .cursorrules file")
        return 0

    print(f"Available agents ({len(agents)}):\n")

    for name in sorted(agents):
        info = get_agent_info(name)
        if info:
            print(f"  • {name}")
            if "description" in info:
                desc = info["description"]
                if len(desc) > 70:
                    desc = desc[:67] + "..."
                print(f"    {desc}")

    return 0


def main():
    """Main CLI entry point - wrapper around cursor-agent."""

    # Create parser for cursor-subagent specific options
    parser = argparse.ArgumentParser(
        prog='cursor-subagent',
        description='Transparent wrapper for cursor-agent with isolated agent configurations',
        add_help=False  # We'll handle help ourselves
    )

    parser.add_argument('-a', '--agent', dest='agent', metavar='NAME',
                        help='Use a specific agent configuration')
    parser.add_argument('-v', '--version', action='store_true',
                        help='Output the version number')
    parser.add_argument('-h', '--help', action='store_true',
                        help='Display help')

    # Parse known args, keep the rest for forwarding
    args, remaining = parser.parse_known_args()

    # Handle cursor-subagent specific options
    if args.help:
        original_help = get_cursor_agent_help()
        enhanced_help = inject_cursor_subagent_help(original_help)
        print(enhanced_help)
        return 0

    if args.version:
        print(f"cursor-subagent {__version__}")
        print(f"cursor-agent {subprocess.run(['cursor-agent', '--version'], capture_output=True, text=True).stdout.strip()}")
        return 0

    # Check for list-agents command
    if remaining and remaining[0] == 'list-agents':
        return cmd_list_agents()

    # Check for mcp command
    if remaining and remaining[0] == 'mcp-server':
        try:
            run_mcp_server()
            return 0
        except KeyboardInterrupt:
            print("\n👋 MCP server stopped", file=sys.stderr)
            return 0

    # Check dylib exists if using an agent
    if args.agent:
        dylib_path = get_dylib_path()
        if not dylib_path.exists():
            print(f"❌ Dylib not found at {dylib_path}", file=sys.stderr)
            print("This usually means cursor-subagent wasn't installed correctly.", file=sys.stderr)
            print("Try reinstalling: uvx --reinstall cursor-subagent@latest", file=sys.stderr)
            return 1

    # Check cursor-agent exists
    cursor_agent = get_cursor_agent_path()
    if not cursor_agent.exists():
        print(f"❌ cursor-agent not found at {cursor_agent}", file=sys.stderr)
        print("Install Cursor to use cursor-subagent", file=sys.stderr)
        return 1

    # Run with agent or forward to cursor-agent
    if args.agent:
        return run_with_agent(args.agent, remaining)
    else:
        # Forward all remaining args to cursor-agent
        try:
            result = subprocess.run(
                [str(cursor_agent)] + remaining,
                check=False
            )
            return result.returncode
        except KeyboardInterrupt:
            return 130
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    sys.exit(main())
