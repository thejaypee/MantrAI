from __future__ import annotations

import tempfile
from pathlib import Path

from click.testing import CliRunner

from mantrai.cli.main import cli


class TestCli:
    def test_cli_read(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["read"])
        assert result.exit_code == 0
        assert "Agent Mantra" in result.output

    def test_cli_confirm(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["confirm", "--session-id", "cli-test-1", "--context", "cli_ack"])
        assert result.exit_code == 0
        assert "Confirmed at" in result.output
        assert "cli-test-1" in result.output

    def test_cli_check(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["check", "--session-id", "cli-test-2"])
        assert result.exit_code == 0
        assert "Session: cli-test-2" in result.output

    def test_cli_validate_pass(self):
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("""## Agent Mantra — Follow This At All Times

> **VALID PRINCIPLE.**

---
""")
            f.flush()
            result = runner.invoke(cli, ["validate", f.name])
            assert result.exit_code == 0
            assert "Valid mantra file" in result.output

    def test_cli_validate_fail(self):
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("""Missing header.

> **No principles block.**
""")
            f.flush()
            result = runner.invoke(cli, ["validate", f.name])
            # Should exit 1 because invalid
            assert result.exit_code == 1 or "INVALID" in result.output or "ERROR" in result.output

    def test_cli_log(self):
        runner = CliRunner()
        # First confirm something
        runner.invoke(cli, ["confirm", "--session-id", "cli-test-3"])
        result = runner.invoke(cli, ["log", "--session-id", "cli-test-3", "--limit", "5"])
        assert result.exit_code == 0
        assert "Compliance log for cli-test-3" in result.output
