from __future__ import annotations

from unittest.mock import patch

from mantrai.core.mantra import get_default_mantra
from mantrai.mempalace_bridge.bridge import (
    get_combined_mantra,
    get_mantra_from_mempalace,
    search_mempalace_cli,
)


class TestMemPalaceBridge:
    def test_bridge_fallback_to_local(self):
        # When mempalace is unavailable, get_combined_mantra returns default
        with patch("mantrai.mempalace_bridge.bridge.search_mempalace_cli", return_value=None):
            mantra = get_combined_mantra()
            assert mantra is not None
            assert len(mantra.principles) >= 7

    def test_bridge_search_cli_returns_none_when_unavailable(self):
        # CLI mode should gracefully return None if mempalace CLI is not installed
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = search_mempalace_cli()
            assert result is None

    def test_bridge_search_cli_parses_output(self):
        fake_output = """## Agent Mantra — Follow This At All Times

> **CUSTOM FROM MEMPALACE.**

---
"""
        with patch(
            "subprocess.run",
            return_value=type("R", (), {"returncode": 0, "stdout": fake_output.strip()})(),
        ):
            result = search_mempalace_cli()
            assert result is not None
            assert "CUSTOM FROM MEMPALACE" in result

    def test_bridge_combined_uses_mempalace_when_available(self):
        fake_output = """## Agent Mantra — Follow This At All Times

> **FROM PALACE.**

---
"""
        with patch("mantrai.mempalace_bridge.bridge.search_mempalace_cli", return_value=fake_output):
            mantra = get_combined_mantra()
            assert mantra is not None
            assert any("FROM PALACE" in p.text for p in mantra.principles)
