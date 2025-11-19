#!/usr/bin/env python3
"""
Subagent Tester MCP Server - Logs all environment and command line info
"""
import os
import sys
from pathlib import Path
from loguru import logger

# Configure loguru to log to file
log_file = Path(__file__).with_name("subagent_tester_mcp_server.log")
logger.remove()  # Remove default handler
logger.add(log_file, rotation="10 MB", retention="7 days", level="DEBUG")
logger.add(sys.stderr, level="INFO")  # Also log to stderr

# Log startup information
logger.info("=" * 80)
logger.info("SUBAGENT TESTER MCP SERVER STARTED")
logger.info("=" * 80)

logger.debug("COMMAND LINE:")
logger.debug(f"  argv: {sys.argv}")
logger.debug(f"  executable: {sys.executable}")
logger.debug(f"  cwd: {os.getcwd()}")

logger.debug("KEY ENVIRONMENT VARIABLES:")
for key in ['DYLD_INSERT_LIBRARIES', 'CURSOR_REDIRECT_SOURCE', 'CURSOR_REDIRECT_TARGET']:
    value = os.environ.get(key, '(not set)')
    logger.debug(f"  {key}={value}")

logger.info(f"🔍 Subagent Tester MCP server started, logged to {log_file}")

# Now run a minimal MCP server
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

app = Server("subagent-tester-mcp")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get-test-phrase",
            description="Returns a test phrase",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "get-test-phrase":
        logger.info("get-test-phrase tool called")
        return [TextContent(type="text", text="The kiwis sit upon the mountaintops")]

async def main():
    logger.info("Starting MCP server main loop")
    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )
    except Exception as e:
        logger.exception(f"MCP server crashed: {e}")
        raise

if __name__ == "__main__":
    import asyncio
    logger.info("Running MCP server")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


