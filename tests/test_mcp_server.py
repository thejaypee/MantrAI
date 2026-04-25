from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest

from mantrai.mcp_server.server import (
    mantrai_check,
    mantrai_compliance_log,
    mantrai_confirm,
    mantrai_inject,
    mantrai_read,
    mantrai_set_level,
    mantrai_validate_custom,
)


class TestMcpTools:
    def test_mantrai_read(self):
        result = mantrai_read()
        assert "Level: normal" in result
        assert "MAKE NO MISTAKES" in result

    def test_mantrai_confirm(self):
        result = mantrai_confirm("test-session-1", action_context="test_ack")
        assert "Confirmed at" in result
        assert "test-session-1" in result

    def test_mantrai_check(self):
        # First confirm so there's data
        mantrai_confirm("test-session-2", action_context="setup")
        result = mantrai_check("test-session-2")
        assert "Session: test-session-2" in result
        assert "Level: normal" in result

    def test_mantrai_inject(self):
        result = mantrai_inject("test-session-3")
        assert "MANTRA INJECTION REQUIRED" in result or "No injection needed" in result

    def test_mantrai_compliance_log(self):
        mantrai_confirm("test-session-4", action_context="log_test")
        result = mantrai_compliance_log("test-session-4", limit=5)
        assert "Compliance log for test-session-4" in result
        assert "log_test" in result

    def test_mantrai_set_level(self):
        result = mantrai_set_level("test-session-5", "strict")
        assert "Level set to 'strict'" in result
        assert "Threshold: 1" in result

        result = mantrai_set_level("test-session-5", "off")
        assert "Level set to 'off'" in result

    def test_mantrai_set_level_invalid(self):
        result = mantrai_set_level("test-session-6", "invalid")
        assert "Invalid level" in result

    def test_tool_list_exists(self):
        from mantrai.mcp_server.server import mcp

        names = list(mcp._tool_manager._tools.keys())
        assert "mantrai_read" in names
        assert "mantrai_confirm" in names
        assert "mantrai_check" in names
        assert "mantrai_inject" in names
        assert "mantrai_compliance_log" in names
        assert "mantrai_set_level" in names
        assert "mantrai_validate_custom" in names
