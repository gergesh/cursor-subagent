#!/usr/bin/env python3
"""
MCP Server for cursor-subagent - provides tools for AI agents.

Entry point: cursor-subagent mcp-server
"""

import json
import subprocess
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .core import (
    list_agents,
    get_agent_info,
    create_agent,
    run_with_agent
)


# Create the MCP server
app = Server("cursor-subagent")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="list-agents",
            description="List all available Cursor agent configurations",
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
                            "(e.g., 'designer' for UI/UX, 'backend' for APIs, 'frontend' for React)"
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
                "required": ["name", "prompt"]
            }
        ),
        Tool(
            name="create-agent",
            description="Create a new agent with a basic configuration structure",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the new agent"
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of the agent's purpose and expertise"
                    }
                },
                "required": ["name", "description"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""

    if name == "list-agents":
        agents = list_agents()

        if not agents:
            return [TextContent(
                type="text",
                text="No agents found. Create one using the create-agent tool."
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

        # Build cursor-agent command
        cursor_args = ["-p", prompt, "--output-format=text", "--force", "--approve-mcps"]
        if model:
            cursor_args.extend(["--model", model])

        # Run with agent (this will block and return the output)
        # We need to capture output, so let's use subprocess directly
        from .core import get_agents_dir, get_dylib_path, get_cursor_agent_path, get_project_root
        import sys

        agent_path = get_agents_dir() / agent_name
        if not agent_path.exists():
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": f"Agent '{agent_name}' does not exist"
                }, indent=2)
            )]

        dylib_path = get_dylib_path()
        if not dylib_path.exists():
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": f"Dylib not found. Run 'cursor-subagent --build' first."
                }, indent=2)
            )]

        import os
        env = os.environ.copy()
        env["DYLD_INSERT_LIBRARIES"] = str(dylib_path)
        env["CURSOR_REDIRECT_TARGET"] = str(agent_path)
        env["CURSOR_REDIRECT_SOURCE"] = str(get_project_root() / ".cursor")

        cursor_agent = get_cursor_agent_path()
        cmd = [str(cursor_agent)] + cursor_args

        try:
            result = subprocess.run(
                cmd,
                env=env,
                cwd=str(get_project_root()),
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0:
                response = {
                    "success": True,
                    "agent": agent_name,
                    "result": result.stdout.strip(),
                    "model": model or "default"
                }
            else:
                response = {
                    "success": False,
                    "agent": agent_name,
                    "error": f"cursor-agent failed: {result.stderr.strip()}",
                    "returncode": result.returncode
                }

            return [TextContent(
                type="text",
                text=json.dumps(response, indent=2)
            )]

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

    elif name == "create-agent":
        result = create_agent(
            name=arguments["name"],
            description=arguments["description"]
        )

        if result["success"]:
            text = (
                f"✅ {result['message']}\n"
                f"Path: {result['path']}\n\n"
                f"Next steps:\n"
                f"1. Edit .cursorrules to customize behavior\n"
                f"2. Add MCP servers to mcp.json if needed\n"
                f"3. Use spawn-agent to execute tasks"
            )
        else:
            text = f"❌ Error: {result['error']}"

        return [TextContent(type="text", text=text)]

    else:
        return [TextContent(
            type="text",
            text=f"Unknown tool: {name}"
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
