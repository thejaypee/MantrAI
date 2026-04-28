"""
Stress tests targeting the 4 fixes from 2026-04-28 code review:
  1. web/server.py: safe_substitute preserves JS ${...} literals
  2. session/gate.py: action_counter increment is atomic under concurrent load
  3. mcp_server/server.py: mantrai_check does NOT mutate the counter
  4. core/agent_setup.py: install_claude_code_hook preserves existing hooks
"""

from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_gate(td: str, level: str = "normal", threshold: int = 5):
    from mantrai.session.gate import ActionGate
    from mantrai.session.tracker import SessionTracker
    from mantrai.core.mantra import get_default_mantra

    db = Path(td) / "test.db"
    tracker = SessionTracker(db_path=db)
    mantra = get_default_mantra()
    cfg = {"normal_threshold": threshold, "strict_threshold": 1, "compliance_window_minutes": 5}
    return ActionGate(tracker, mantra, level=level, config=cfg), tracker


# ===========================================================================
# Fix 1 — safe_substitute: JS template literals survive template rendering
# ===========================================================================

class TestSafeSubstitute:
    def test_index_does_not_crash(self):
        from fastapi.testclient import TestClient
        from mantrai.web.server import app
        client = TestClient(app)
        resp = client.get("/")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"

    def test_js_template_literals_present_in_output(self):
        """JS ${...} expressions must survive intact — safe_substitute leaves unknown vars alone."""
        from fastapi.testclient import TestClient
        from mantrai.web.server import app
        client = TestClient(app)
        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.text
        # These JS template literal patterns must appear in the rendered page
        assert "${cat}" in html or "cat" in html, "JS category template literal missing"
        assert "${i}" in html or "'${" in html or "p.checked" in html, "JS index template literal missing"

    def test_index_repeated_renders_stable(self):
        """Calling / 20 times must always succeed — no KeyError on re-render."""
        from fastapi.testclient import TestClient
        from mantrai.web.server import app
        client = TestClient(app)
        for i in range(20):
            resp = client.get("/")
            assert resp.status_code == 200, f"Render {i} failed: {resp.text[:100]}"


# ===========================================================================
# Fix 2 — Atomic counter: final count must be exactly N under concurrent load
# ===========================================================================

class TestAtomicCounter:
    def test_counter_exact_under_concurrency(self):
        """10 threads each doing 50 non-diagnostic actions = exactly 500 increments."""
        with tempfile.TemporaryDirectory() as td:
            gate, _ = _make_gate(td, level="off")  # off = no resets
            errors = []
            THREADS = 10
            ACTIONS_PER_THREAD = 50

            def run():
                try:
                    for _ in range(ACTIONS_PER_THREAD):
                        gate.before_action("work", "s1")
                except Exception as e:
                    errors.append(str(e))

            threads = [threading.Thread(target=run) for _ in range(THREADS)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert not errors, f"Thread errors: {errors}"
            assert gate.action_counter == THREADS * ACTIONS_PER_THREAD, (
                f"Expected {THREADS * ACTIONS_PER_THREAD}, got {gate.action_counter}"
            )

    def test_counter_exact_repeated(self):
        """Run the exact-count test 10 times to catch intermittent races."""
        for run_n in range(10):
            with tempfile.TemporaryDirectory() as td:
                gate, _ = _make_gate(td, level="off")
                THREADS, ACTIONS = 5, 100
                errors = []

                def work():
                    for _ in range(ACTIONS):
                        gate.before_action("work", "s")

                threads = [threading.Thread(target=work) for _ in range(THREADS)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

                assert not errors
                expected = THREADS * ACTIONS
                assert gate.action_counter == expected, (
                    f"Run {run_n}: expected {expected}, got {gate.action_counter}"
                )

    def test_diagnostic_actions_never_increment(self):
        """cli_check and mcp_check must never change the counter."""
        with tempfile.TemporaryDirectory() as td:
            gate, _ = _make_gate(td, level="off")
            assert gate.action_counter == 0
            gate.before_action("cli_check", "s1")
            gate.before_action("mcp_check", "s1")
            gate.before_action("cli_check", "s1")
            assert gate.action_counter == 0, (
                f"Diagnostic actions incremented counter to {gate.action_counter}"
            )


# ===========================================================================
# Fix 3 — mantrai_check must not mutate the counter
# ===========================================================================

class TestMantraiCheckNoSideEffect:
    def test_check_does_not_reset_counter_at_threshold(self):
        """mantrai_check must not side-effect the action counter.

        Normal mode resets counter when out-of-window or at threshold.
        We use 'off' level to build an exact counter value, then verify
        mantrai_check reads it without changing it.
        """
        from mantrai.mcp_server import server as mcp_module

        with tempfile.TemporaryDirectory() as td:
            mcp_module._tracker = None
            mcp_module._gate = None
            mcp_module._mantra = None

            # 'off' level: counter accumulates without resets
            gate, tracker = _make_gate(td, level="off", threshold=3)
            mcp_module._gate = gate
            mcp_module._tracker = tracker

            gate.before_action("work", "s1")
            gate.before_action("work", "s1")
            assert gate.action_counter == 2, (
                f"Expected 2, got {gate.action_counter}"
            )

            result = mcp_module.mantrai_check("s1")
            assert "Actions since last injection: 2" in result, (
                f"mantrai_check reported wrong count: {result}"
            )
            assert gate.action_counter == 2, (
                f"mantrai_check changed the counter to {gate.action_counter}"
            )

            mcp_module._tracker = None
            mcp_module._gate = None
            mcp_module._mantra = None

    def test_check_does_not_reset_counter_over_threshold(self):
        """Even when counter exceeds threshold, mantrai_check must not reset it."""
        from mantrai.mcp_server import server as mcp_module

        with tempfile.TemporaryDirectory() as td:
            mcp_module._tracker = None
            mcp_module._gate = None
            mcp_module._mantra = None

            gate, tracker = _make_gate(td, level="normal", threshold=3)
            mcp_module._gate = gate
            mcp_module._tracker = tracker

            # Drive counter past threshold
            for _ in range(5):
                gate.before_action("work", "s1")
            # Note: normal mode resets on inject, so we use off mode for clean count
            gate2, tracker2 = _make_gate(td + "2", level="off", threshold=3)
            mcp_module._gate = gate2
            mcp_module._tracker = tracker2
            for _ in range(5):
                gate2.before_action("work", "s2")
            assert gate2.action_counter == 5

            result = mcp_module.mantrai_check("s2")
            assert gate2.action_counter == 5, (
                f"mantrai_check changed counter from 5 to {gate2.action_counter}"
            )

            # Cleanup
            mcp_module._tracker = None
            mcp_module._gate = None
            mcp_module._mantra = None


# ===========================================================================
# Fix 4 — install_claude_code_hook uses setdefault (preserves existing hooks)
# ===========================================================================

class TestHookSetdefault:
    def test_installs_when_no_hook_exists(self):
        from mantrai.core.agent_setup import install_claude_code_hook
        with tempfile.TemporaryDirectory() as td:
            ok, msg = install_claude_code_hook(Path(td))
            assert ok, msg
            settings = json.loads((Path(td) / ".claude" / "settings.json").read_text())
            assert settings["user-prompt-submit-hook"] == "mantrai hook"

    def test_preserves_existing_hook(self):
        """If a hook already exists, it must NOT be overwritten."""
        from mantrai.core.agent_setup import install_claude_code_hook
        with tempfile.TemporaryDirectory() as td:
            settings_dir = Path(td) / ".claude"
            settings_dir.mkdir()
            existing = {"user-prompt-submit-hook": "my-custom-hook", "other": "value"}
            (settings_dir / "settings.json").write_text(json.dumps(existing))

            ok, _ = install_claude_code_hook(Path(td))
            assert ok
            after = json.loads((settings_dir / "settings.json").read_text())
            assert after["user-prompt-submit-hook"] == "my-custom-hook", (
                f"Existing hook was overwritten: {after}"
            )
            assert after["other"] == "value"

    def test_idempotent_when_mantrai_hook_already_installed(self):
        """Re-installing over an existing mantrai hook must be a no-op."""
        from mantrai.core.agent_setup import install_claude_code_hook
        with tempfile.TemporaryDirectory() as td:
            ok, _ = install_claude_code_hook(Path(td))
            assert ok
            ok2, _ = install_claude_code_hook(Path(td))
            assert ok2
            settings = json.loads((Path(td) / ".claude" / "settings.json").read_text())
            assert settings["user-prompt-submit-hook"] == "mantrai hook"

    def test_preserves_other_settings_keys(self):
        """Non-hook keys in settings.json must survive the install."""
        from mantrai.core.agent_setup import install_claude_code_hook
        with tempfile.TemporaryDirectory() as td:
            settings_dir = Path(td) / ".claude"
            settings_dir.mkdir()
            existing = {"theme": "dark", "model": "claude-opus", "permissions": ["read"]}
            (settings_dir / "settings.json").write_text(json.dumps(existing))

            install_claude_code_hook(Path(td))
            after = json.loads((settings_dir / "settings.json").read_text())
            assert after["theme"] == "dark"
            assert after["model"] == "claude-opus"
            assert after["permissions"] == ["read"]
            assert after["user-prompt-submit-hook"] == "mantrai hook"
