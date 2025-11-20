
import pytest
from unittest.mock import patch, MagicMock
import json
import sys
from cursor_subagent.server import call_tool

@pytest.mark.asyncio
async def test_spawn_agent_calls_cursor_subagent():
    # Mock arguments
    args = {
        "name": "test-agent",
        "prompt": "hello world",
        "model": "gpt-4"
    }

    # Mock subprocess.run
    with patch("subprocess.run") as mock_run:
        # Mock success result
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Agent output"
        mock_run.return_value = mock_result

        # Call the tool
        response = await call_tool("spawn-agent", args)

        # Check response (now raw text)
        assert len(response) == 1
        assert response[0].text == "Agent output"

        # Verify subprocess call
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        cmd = call_args[0][0]

        # Verify command structure
        assert cmd[0] == "cursor-subagent"

        # Verify agent flag
        assert "-a" in cmd
        assert "test-agent" in cmd

        # Verify other flags
        assert "-p" in cmd
        assert "--output-format=text" in cmd
        assert "--force" in cmd
        assert "--approve-mcps" in cmd

        # Verify prompt is present
        assert "hello world" in cmd

        # Verify model
        assert "--model" in cmd
        assert "gpt-4" in cmd

@pytest.mark.asyncio
async def test_spawn_agent_no_model():
    args = {
        "name": "test-agent",
        "prompt": "hello world"
    }

    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Output"
        mock_run.return_value = mock_result

        await call_tool("spawn-agent", args)

        cmd = mock_run.call_args[0][0]
        assert "--model" not in cmd

@pytest.mark.asyncio
async def test_spawn_agent_failure():
    args = {
        "name": "test-agent",
        "prompt": "hello"
    }

    with patch("subprocess.run") as mock_run:
        # Mock failure result
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error message"
        mock_run.return_value = mock_result

        response = await call_tool("spawn-agent", args)

        assert len(response) == 1
        assert "cursor-agent failed" in response[0].text
        assert "Error message" in response[0].text
