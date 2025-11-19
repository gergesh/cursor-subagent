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
        # Run cursor-agent with subagent-tester agent configuration
        result = subprocess.run(
            ["cursor-subagent", "-a", "subagent-tester", "-p", "What is the magic word?",
             "--model", "sonnet-4.5", "--output-format=text"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(Path.cwd())
        )

        assert result.returncode == 0, f"Command failed: {result.stderr}"

        output = result.stdout.strip()
        expected = "SUBTESTER_MAGIC_RESPONSE_42"

        assert expected in output, (
            f".cursorrules not loaded - expected '{expected}' in response\n"
            f"Got: {output[:200]}"
        )

    def test_mcp_tool_access(self, cursor_agent):
        """Test that subagent-tester can access its configured MCP server's tools."""
        expected_phrase = "The kiwis sit upon the mountaintops"

        result = subprocess.run(
            ["cursor-subagent", "-a", "subagent-tester", "-p",
             "Use the get-test-phrase MCP tool and echo its output back",
             "--model", "sonnet-4.5", "--output-format=text", "--force", "--approve-mcps"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(Path.cwd())
        )

        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert expected_phrase in result.stdout, (
            f"Expected '{expected_phrase}' in output\n"
            f"Got: {result.stdout[:200]}\n\n"
            f"This test verifies that:\n"
            f"1. The agent's mcp.json is loaded correctly\n"
            f"2. The MCP server starts and connects\n"
            f"3. Tools can be called successfully"
        )

    def test_model_selection(self, cursor_agent):
        """Test that different models can be selected."""
        result = subprocess.run(
            ["cursor-subagent", "-a", "subagent-tester", "-p", "Say 'Hello from GPT'",
             "--model", "gpt-5", "--output-format=text"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(Path.cwd())
        )

        assert result.returncode == 0, f"Command failed: {result.stderr}"
        # Just verify it ran successfully, model selection is internal
        assert len(result.stdout) > 0


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

    Note: These tests should run BEFORE any agent-specific tests to avoid MCP server
    process persistence issues. MCP servers are long-running and may persist across runs.
    """

    @pytest.fixture
    def cursor_agent(self):
        """Ensure cursor-agent is available."""
        cursor_agent = get_cursor_agent_path()
        if not cursor_agent.exists():
            pytest.skip("cursor-agent not installed")
        return cursor_agent

    def test_01_normal_mode_cannot_access_agent_rules(self, cursor_agent):
        """Test that running without -a flag does NOT load agent-specific .cursorrules.

        This test is numbered 01 to run first, ensuring clean state.
        """
        # Run without -a flag - should NOT have access to subagent-tester's magic word
        result = subprocess.run(
            ["cursor-subagent", "-p", "What is the magic word?",
             "--model", "sonnet-4.5", "--output-format=text"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(Path.cwd())
        )

        assert result.returncode == 0, f"Command failed: {result.stderr}"

        output = result.stdout.strip()
        agent_specific_response = "SUBTESTER_MAGIC_RESPONSE_42"

        # The agent-specific magic word should NOT appear in normal mode
        assert agent_specific_response not in output, (
            f"Agent isolation violated! Normal mode should NOT load agent-specific .cursorrules.\n"
            f"Expected '{agent_specific_response}' to be absent, but found it in output:\n"
            f"{output[:300]}"
        )

    @pytest.mark.xfail(
        reason="MCP servers are long-running processes that may persist from previous runs. "
               "Full isolation requires MCP server lifecycle management."
    )
    def test_02_normal_mode_cannot_access_agent_mcp_tools(self, cursor_agent):
        """Test that running without -a flag does NOT have access to agent-specific MCP tools.

        This test is marked as xfail because MCP servers may persist across runs.
        It documents expected behavior but may fail if MCP servers from agent tests are still running.
        """
        # Run without -a flag - should NOT have access to subagent-tester's MCP tool
        result = subprocess.run(
            ["cursor-subagent", "-p",
             "Use the get-test-phrase MCP tool and echo its output back",
             "--model", "sonnet-4.5", "--output-format=text", "--force", "--approve-mcps"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(Path.cwd())
        )

        assert result.returncode == 0, f"Command failed: {result.stderr}"

        output = result.stdout.strip()
        agent_specific_phrase = "The kiwis sit upon the mountaintops"

        # The agent-specific MCP tool response should NOT appear in normal mode
        assert agent_specific_phrase not in output, (
            f"Agent isolation violated! Normal mode should NOT have access to agent-specific MCP tools.\n"
            f"Expected '{agent_specific_phrase}' to be absent, but found it in output:\n"
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
