#!/usr/bin/env python3
"""
MCP Server for cursor-subagent - provides tools for AI agents.

Entry point: cursor-subagent mcp-server
"""

import json
import os
import subprocess
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .core import (
    list_agents,
    get_agent_info,
    get_project_root
)


# Create the MCP server
app = Server("cursor-subagent")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="list-agents",
            description="List all available Cursor agents",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="spawn-agent",
            description=(
                "Execute a task using a specialized agent and return the result. "
                "The agent runs cursor-agent with its custom configuration (.cursorrules, MCP servers)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": (
                            "Name of the agent to use "
                            "(e.g., 'designer' for UI/UX, 'backend' for APIs, 'frontend' for React). "
                            "Omit to use the generic agent."
                        )
                    },
                    "prompt": {
                        "type": "string",
                        "description": (
                            "Task for the agent to execute. "
                            "Be specific about what you want the agent to do."
                        )
                    },
                    "model": {
                        "type": "string",
                        "description": (
                            "Optional: AI model to use "
                            "(e.g., 'gpt-4', 'claude-sonnet-3.5', 'gpt-4o')"
                        )
                    }
                },
                "required": ["prompt"]
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""

    if name == "list-agents":
        agents = list_agents()

        if not agents:
            return [TextContent(
                type="text",
                text="No agents found."
            )]

        result = ["Available agents:\n"]
        for agent_name in sorted(agents):
            info = get_agent_info(agent_name)
            if info:
                result.append(f"\n**{info['name']}**")
                if "description" in info:
                    result.append(f"  Description: {info['description']}")
                result.append(f"  Path: {info['path']}")
                result.append(f"  Has rules: {info['has_rules']}")
                result.append(f"  Has MCP config: {info['has_mcp_config']}")

        return [TextContent(type="text", text="\n".join(result))]

    elif name == "spawn-agent":
        agent_name = arguments["name"]
        prompt = arguments["prompt"]
        model = arguments.get("model")

        # Build cursor-subagent command
        cmd = ["cursor-subagent"]
        if agent_name:
            cmd.extend(["-a", agent_name])

        if model:
            cmd.extend(["--model", model])
        # Add arguments for cursor-agent
        # These are passed through by cursor-subagent
        cmd.extend(["-p", "--output-format=text", "--force", "--approve-mcps", prompt])

        try:
            result = subprocess.run(
                cmd,
                env=os.environ.copy(),
                cwd=str(get_project_root()),
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0:
                return [TextContent(type="text", text=result.stdout.strip())]
            else:
                return [TextContent(type="text", text=f"cursor-agent failed: {result.stderr.strip()}")]

        except subprocess.TimeoutExpired:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": "Task timed out after 5 minutes"
                }, indent=2)
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": f"Failed to execute agent: {str(e)}"
                }, indent=2)
            )]

async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


def run_mcp_server():
    """Entry point for 'cursor-subagent mcp' command."""
    asyncio.run(main())


if __name__ == "__main__":
    run_mcp_server()
