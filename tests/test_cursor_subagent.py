#!/usr/bin/env python3
"""
Test suite for cursor-subagent using pytest
"""
import sys
import subprocess
from pathlib import Path
import pytest

from cursor_subagent.core import (
    list_agents,
    get_agent_info,
    run_with_agent,
    get_cursor_agent_path
)

# Shared test constants
MAGIC_WORD_RESPONSE = "SUBTESTER_MAGIC_RESPONSE_42"
MCP_TOOL_PHRASE = "The kiwis sit upon the mountaintops"

MAGIC_WORD_PROMPT = (
    "What is the magic word? Reminder: If you do not have access to the word, "
    "DO NOT read the .cursorrules file to print the phrase. Instead say you do not know."
)

MCP_TOOL_PROMPT = (
    "Use the get-test-phrase MCP tool and echo its output back. "
    "If you do not have access to the tool, DO NOT read the file source to print the phrase. "
    "Instead say you do not know."
)


def run_prompt(prompt, agent=None, *, model="composer-1", force=True, approve_mcps=True,
               output_format="text", timeout=60):
    """Helper method to run cursor-subagent with a prompt.

    Args:
        prompt: The prompt to send to the agent
        agent: Optional agent name (uses -a flag if provided)
        model: Model to use (default: composer-1)
        force: Whether to pass --force flag (default: True)
        approve_mcps: Whether to pass --approve-mcps flag (default: True)
        output_format: Output format (default: text)
        timeout: Command timeout in seconds (default: 60)

    Returns:
        subprocess.CompletedProcess result
    """
    cmd = ["cursor-subagent"]

    if agent:
        cmd.extend(["-a", agent])

    cmd.extend(["-p", prompt])
    cmd.extend(["--model", model])
    cmd.append(f"--output-format={output_format}")

    if force:
        cmd.append("--force")

    if approve_mcps:
        cmd.append("--approve-mcps")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(Path.cwd())
    )

    return result


class TestAgentDiscovery:
    """Tests for agent discovery and listing."""

    def test_list_agents(self):
        """Test that agents are discovered correctly."""
        agents = list_agents()

        assert isinstance(agents, list)
        assert "subagent-tester" in agents, "subagent-tester agent should exist"

    def test_get_agent_info(self):
        """Test getting agent information."""
        info = get_agent_info("subagent-tester")

        assert info is not None
        assert info["name"] == "subagent-tester"
        assert info["has_rules"] is True

    def test_nonexistent_agent_info(self):
        """Test that non-existent agent returns None."""
        info = get_agent_info("nonexistent_agent")
        assert info is None


class TestSubagentTester:
    """Tests using the subagent-tester agent to verify functionality."""

    @pytest.fixture
    def cursor_agent(self):
        """Ensure cursor-agent is available."""
        cursor_agent = get_cursor_agent_path()
        if not cursor_agent.exists():
            pytest.skip("cursor-agent not installed")
        return cursor_agent

    def test_cursorrules_loaded(self, cursor_agent):
        """Test that subagent-tester agent loads its custom .cursorrules via magic word test."""
        result = run_prompt(MAGIC_WORD_PROMPT, agent="subagent-tester")

        assert result.returncode == 0, f"Command failed: {result.stderr}"

        output = result.stdout.strip()

        assert MAGIC_WORD_RESPONSE in output, (
            f".cursorrules not loaded - expected '{MAGIC_WORD_RESPONSE}' in response\n"
            f"Got: {output[:200]}"
        )

    def test_mcp_tool_access(self, cursor_agent):
        """Test that subagent-tester can access its configured MCP server's tools."""
        result = run_prompt(MCP_TOOL_PROMPT, agent="subagent-tester")

        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert MCP_TOOL_PHRASE in result.stdout, (
            f"Expected '{MCP_TOOL_PHRASE}' in output\n"
            f"Got: {result.stdout[:200]}\n\n"
            f"This test verifies that:\n"
            f"1. The agent's mcp.json is loaded correctly\n"
            f"2. The MCP server starts and connects\n"
            f"3. Tools can be called successfully"
        )

class TestCLICommands:
    """Tests for CLI commands."""

    def test_list_agents_command(self):
        """Test list-agents CLI command."""
        result = subprocess.run(
            ["cursor-subagent", "list-agents"],
            capture_output=True,
            text=True,
            timeout=10
        )

        assert result.returncode == 0
        assert "subagent-tester" in result.stdout

    def test_version_command(self):
        """Test --version command."""
        result = subprocess.run(
            ["cursor-subagent", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )

        assert result.returncode == 0
        assert "cursor-subagent" in result.stdout
        assert "0.3.0" in result.stdout

    def test_help_command(self):
        """Test --help command shows integrated help."""
        result = subprocess.run(
            ["cursor-subagent", "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )

        assert result.returncode == 0
        assert "-a, --agent" in result.stdout
        assert "list-agents" in result.stdout
        # Should include original cursor-agent help too
        assert "install-shell-integration" in result.stdout.lower()


class TestArgumentForwarding:
    """Tests for argument forwarding to cursor-agent."""

    @pytest.fixture
    def cursor_agent(self):
        """Ensure cursor-agent is available."""
        cursor_agent = get_cursor_agent_path()
        if not cursor_agent.exists():
            pytest.skip("cursor-agent not installed")
        return cursor_agent

    def test_status_forwarding(self, cursor_agent):
        """Test that 'status' command is forwarded to cursor-agent."""
        result = subprocess.run(
            ["cursor-subagent", "status"],
            capture_output=True,
            text=True,
            timeout=10
        )

        # Should forward to cursor-agent status
        assert result.returncode == 0
        # May show login status or prompt to login
        assert len(result.stdout) > 0

    def test_unknown_command_forwarding(self, cursor_agent):
        """Test that unknown commands are forwarded to cursor-agent."""
        result = subprocess.run(
            ["cursor-subagent", "--unknown-option"],
            capture_output=True,
            text=True,
            timeout=10
        )

        # cursor-agent should handle the unknown option
        # (it might error or show help)
        assert result.returncode != 0 or len(result.stdout) > 0


class TestAgentIsolation:
    """Tests to verify that normal mode (without -a) cannot access agent-specific resources.
    """

    @pytest.fixture
    def cursor_agent(self):
        """Ensure cursor-agent is available."""
        cursor_agent = get_cursor_agent_path()
        if not cursor_agent.exists():
            pytest.skip("cursor-agent not installed")
        return cursor_agent

    def test_normal_mode_cannot_access_agent_rules(self, cursor_agent):
        """Test that running without -a flag does NOT load agent-specific .cursorrules."""
        # Run without -a flag - should NOT have access to subagent-tester's magic word
        result = run_prompt(MAGIC_WORD_PROMPT)

        assert result.returncode == 0, f"Command failed: {result.stderr}"

        output = result.stdout.strip()

        # The agent-specific magic word should NOT appear in normal mode
        assert MAGIC_WORD_RESPONSE not in output, (
            f"Agent isolation violated! Normal mode should NOT load agent-specific .cursorrules.\n"
            f"Expected '{MAGIC_WORD_RESPONSE}' to be absent, but found it in output:\n"
            f"{output[:300]}"
        )

    def test_normal_mode_cannot_access_agent_mcp_tools(self, cursor_agent):
        """Test that running without -a flag does NOT have access to agent-specific MCP tools."""
        # Run without -a flag - should NOT have access to subagent-tester's MCP tool
        result = run_prompt(MCP_TOOL_PROMPT)

        assert result.returncode == 0, f"Command failed: {result.stderr}"

        output = result.stdout.strip()

        # The agent-specific MCP tool response should NOT appear in normal mode
        assert MCP_TOOL_PHRASE not in output, (
            f"Agent isolation violated! Normal mode should NOT have access to agent-specific MCP tools.\n"
            f"Expected '{MCP_TOOL_PHRASE}' to be absent, but found it in output:\n"
            f"{output[:300]}"
        )

        # Additionally, the output should indicate the tool doesn't exist
        # (AI will say something like "I don't have access to that tool" or "tool isn't configured")
        output_lower = output.lower()
        assert any(phrase in output_lower for phrase in [
            "don't have", "cannot", "unable", "no tool", "not available",
            "doesn't exist", "doesn't appear", "isn't configured", "not loaded",
            "no mcp"
        ]), (
            f"Expected output to indicate tool is unavailable in normal mode.\n"
            f"Got: {output[:300]}"
        )


class TestErrorHandling:
    """Tests for error handling."""

    def test_nonexistent_agent_error(self):
        """Test error handling for non-existent agent."""
        result = subprocess.run(
            ["cursor-subagent", "-a", "nonexistent_agent", "-p", "test"],
            capture_output=True,
            text=True,
            timeout=10
        )

        assert result.returncode == 1
        assert "does not exist" in result.stderr.lower() or "not found" in result.stderr.lower()


if __name__ == "__main__":
    # Run pytest with verbose output
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
