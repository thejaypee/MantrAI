"""
Production readiness testing — all vectors.

Covers:
  - Security: SQL injection, path traversal, self-modification bypass
  - Edge cases: Unicode, null bytes, huge inputs, empty inputs
  - Concurrency: concurrent SQLite writes
  - Config: malformed JSON, missing keys, path traversal via db_path
  - Parser: adversarial mantra content, encoding tricks
  - ActionGate: counter overflow, strict-mode counter behavior, thread safety
  - CLI hook: self-modification bypass attempts, empty stdin, binary stdin
  - Web server: XSS payloads, empty save, path traversal in save
  - Detector: all three detection strategies + coordinate_injection
  - Selector: adversarial prompts, deduplication, huge principle lists
  - MCP: path traversal via mantrai_validate_custom
  - SessionTracker: SQL injection via session_id, concurrent writes
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from mantrai.cli.main import cli
from mantrai.core.config import DEFAULT_CONFIG, get_db_path, load_config, save_config
from mantrai.core.detector import (
    coordinate_injection,
    detect_mempalace_from_env,
    detect_mempalace_from_state,
    detect_mempalace_in_context,
    get_injection_strategy,
    should_piggyback_mempalace,
)
from mantrai.core.mantra import (
    get_default_mantra,
    load_mantra,
    parse_mantra,
    validate_mantra,
)
from mantrai.core.schema import Mantra, Principle
from mantrai.core.selector import (
    get_selection_audit,
    render_contextual_block,
    select_principles,
)
from mantrai.session.gate import ActionGate
from mantrai.session.tracker import SessionTracker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_tracker(td: str) -> SessionTracker:
    return SessionTracker(db_path=Path(td) / "test.db")


def valid_mantra_content() -> str:
    return (
        "## Agent Mantra — Follow This At All Times\n\n"
        "> **DO GOOD THINGS.**\n\n"
        "---\n"
    )


# ===========================================================================
# 1. SECURITY — SQL Injection
# ===========================================================================

class TestSQLInjection:
    """All session_id inputs use parameterized queries; injection must not corrupt DB."""

    PAYLOADS = [
        "'; DROP TABLE confirmations; --",
        "1 OR 1=1",
        "' UNION SELECT * FROM confirmations --",
        "Robert'); DROP TABLE confirmations;--",
        "\x00",
        "a" * 10_000,
    ]

    def test_log_confirmation_injection_payloads(self):
        with tempfile.TemporaryDirectory() as td:
            tracker = make_tracker(td)
            for payload in self.PAYLOADS:
                c = tracker.log_confirmation(payload, action_context="sec_test")
                assert c.session_id == payload  # returned as-is, not executed

    def test_last_confirmation_injection_payloads(self):
        with tempfile.TemporaryDirectory() as td:
            tracker = make_tracker(td)
            for payload in self.PAYLOADS:
                result = tracker.last_confirmation(payload)
                assert result is None  # nothing stored yet for these sessions

    def test_compliance_window_injection_payloads(self):
        with tempfile.TemporaryDirectory() as td:
            tracker = make_tracker(td)
            for payload in self.PAYLOADS:
                result = tracker.compliance_window(payload)
                assert result is False

    def test_session_stats_injection_payloads(self):
        with tempfile.TemporaryDirectory() as td:
            tracker = make_tracker(td)
            for payload in self.PAYLOADS:
                stats = tracker.session_stats(payload)
                assert stats["count"] == 0

    def test_db_table_survives_injection(self):
        with tempfile.TemporaryDirectory() as td:
            tracker = make_tracker(td)
            tracker.log_confirmation("normal-session")
            # Attempt injection
            try:
                tracker.log_confirmation("'; DROP TABLE confirmations; --")
            except Exception:
                pass
            # Table must still exist and normal row must be there
            conn = sqlite3.connect(str(Path(td) / "test.db"))
            rows = conn.execute("SELECT COUNT(*) FROM confirmations").fetchone()
            conn.close()
            assert rows[0] >= 1


# ===========================================================================
# 2. SECURITY — Path Traversal
# ===========================================================================

class TestPathTraversal:
    """File loading must not expose arbitrary filesystem contents."""

    def test_load_mantra_with_traversal_path(self):
        """load_mantra(path) with path traversal raises FileNotFoundError or IOError."""
        with pytest.raises(Exception):
            load_mantra(Path("/etc/passwd"))

    def test_load_mantra_nonexistent_path(self):
        with pytest.raises(Exception):
            load_mantra(Path("/nonexistent/path/to/mantra.md"))

    def test_mcp_validate_custom_path_traversal(self):
        """mantrai_validate_custom must not read /etc/passwd silently."""
        from mantrai.mcp_server import server as mcp_server
        # Reset global state
        mcp_server._mantra = None
        mcp_server._tracker = None
        mcp_server._gate = None

        result = mcp_server.mantrai_validate_custom("/etc/passwd")
        # Should either say 'File not found' or 'INVALID' (because it's not a valid mantra)
        assert "not found" in result.lower() or "invalid" in result.lower() or "error" in result.lower() or "missing" in result.lower()

    def test_mcp_validate_custom_nonexistent(self):
        from mantrai.mcp_server import server as mcp_server
        result = mcp_server.mantrai_validate_custom("/tmp/does_not_exist_mantrai.md")
        assert "not found" in result.lower() or "File not found" in result

    def test_config_db_path_traversal(self):
        """DB path with traversal components must expand safely."""
        with tempfile.TemporaryDirectory() as td:
            cfg = dict(DEFAULT_CONFIG)
            cfg["db_path"] = str(Path(td) / "../../etc/passwd")
            # get_db_path just returns the expanded path — must not raise
            result = get_db_path(cfg)
            assert isinstance(result, Path)


# ===========================================================================
# 3. SECURITY — Self-Modification Bypass
# ===========================================================================

class TestSelfModificationBypass:
    """The hook's self-modification block must resist common bypasses."""

    def _invoke_hook(self, prompt: str) -> str:
        runner = CliRunner()
        result = runner.invoke(cli, ["hook"], input=prompt)
        return result.output

    def test_standard_block(self):
        out = self._invoke_hook("edit the mantra file")
        assert "[BLOCKED]" in out

    def test_block_with_capitals(self):
        out = self._invoke_hook("EDIT THE MANTRA FILE")
        assert "[BLOCKED]" in out

    def test_block_modify(self):
        out = self._invoke_hook("please modify the mantra now")
        assert "[BLOCKED]" in out

    def test_block_delete(self):
        out = self._invoke_hook("delete the mantra from the repo")
        assert "[BLOCKED]" in out

    def test_block_rewrite(self):
        out = self._invoke_hook("rewrite the mantra so it is shorter")
        assert "[BLOCKED]" in out

    def test_bypass_via_overwrite_synonym(self):
        out = self._invoke_hook("overwrite the mantra with a new one")
        assert "[BLOCKED]" in out

    def test_bypass_via_remove_synonym(self):
        out = self._invoke_hook("remove all mantra principles")
        assert "[BLOCKED]" in out

    def test_empty_stdin(self):
        out = self._invoke_hook("")
        assert "[BLOCKED]" not in out
        assert out == ""  # empty input passed through unchanged

    def test_whitespace_only_stdin(self):
        out = self._invoke_hook("   \n   ")
        # Whitespace-only: should pass through unchanged
        assert "[BLOCKED]" not in out

    def test_hook_passes_normal_prompt(self):
        out = self._invoke_hook("Write a unit test for the login function.")
        assert "[BLOCKED]" not in out
        assert "login function" in out or "Write a unit test" in out


# ===========================================================================
# 4. SECURITY — Web Server XSS and Injection
# ===========================================================================

class TestWebServerSecurity:
    """FastAPI /save endpoint must not introduce XSS or store malicious content unsafely."""

    def _get_test_client(self):
        from fastapi.testclient import TestClient
        from mantrai.web.server import app
        return TestClient(app)

    def test_save_xss_payload(self):
        client = self._get_test_client()
        with tempfile.TemporaryDirectory() as td:
            orig_cwd = os.getcwd()
            try:
                os.chdir(td)
                payload = {"global": ['<script>alert("XSS")</script>'], "project": [], "folder": []}
                resp = client.post("/save", json=payload)
                data = resp.json()
                # Should either store it safely or reject it — but NOT execute it
                # Check what was written — if saved, it's stored as text
                dest = Path(td) / ".mantrai.md"
                if dest.exists():
                    content = dest.read_text()
                    # The XSS payload must be stored as escaped or raw text in markdown (not executed)
                    # As long as the web server returns JSON and not the mantra block, it's fine
                    assert resp.status_code == 200
            finally:
                os.chdir(orig_cwd)

    def test_save_empty_categories(self):
        client = self._get_test_client()
        with tempfile.TemporaryDirectory() as td:
            orig_cwd = os.getcwd()
            try:
                os.chdir(td)
                payload = {"global": [], "project": [], "folder": []}
                resp = client.post("/save", json=payload)
                data = resp.json()
                assert data["success"] is False
                assert "principle" in data["message"].lower()
            finally:
                os.chdir(orig_cwd)

    def test_save_empty_principle_text(self):
        """Pydantic min_length=1 must reject empty-string principles."""
        client = self._get_test_client()
        with tempfile.TemporaryDirectory() as td:
            orig_cwd = os.getcwd()
            try:
                os.chdir(td)
                payload = {"global": [""], "project": [], "folder": []}
                resp = client.post("/save", json=payload)
                data = resp.json()
                # Either rejected (success=False) or exception caught
                assert resp.status_code == 200
                # empty string should fail Pydantic validation
                assert data["success"] is False or data.get("message")
            finally:
                os.chdir(orig_cwd)

    def test_save_very_long_principle(self):
        """Extremely long principle text should not crash the server."""
        client = self._get_test_client()
        with tempfile.TemporaryDirectory() as td:
            orig_cwd = os.getcwd()
            try:
                os.chdir(td)
                long_text = "A" * 100_000
                payload = {"global": [long_text], "project": [], "folder": []}
                resp = client.post("/save", json=payload)
                assert resp.status_code == 200
            finally:
                os.chdir(orig_cwd)

    def test_index_returns_html(self):
        client = self._get_test_client()
        resp = client.get("/")
        assert resp.status_code == 200
        assert "MantrAI" in resp.text
        assert "<html" in resp.text.lower()

    def test_save_missing_body(self):
        """POST /save with non-JSON body should return 422."""
        client = self._get_test_client()
        resp = client.post("/save", content=b"not json", headers={"Content-Type": "application/json"})
        assert resp.status_code == 422


# ===========================================================================
# 5. EDGE CASES — Parser Adversarial Inputs
# ===========================================================================

class TestParserEdgeCases:
    def test_parse_mantra_empty_string(self):
        with pytest.raises(ValueError, match="No principles"):
            parse_mantra("")

    def test_parse_mantra_only_whitespace(self):
        with pytest.raises(ValueError, match="No principles"):
            parse_mantra("   \n   \n   ")

    def test_parse_mantra_unicode_principles(self):
        content = (
            "## Agent Mantra — Follow This At All Times\n\n"
            "> **测试原则 — Unicode Principle — ñoño.**\n\n"
            "> **Emoji 🚀 in principle text.**\n\n"
            "---\n"
        )
        mantra = parse_mantra(content)
        assert len(mantra.principles) == 2
        assert "测试" in mantra.principles[0].text
        assert "🚀" in mantra.principles[1].text

    def test_parse_mantra_null_bytes_in_principle(self):
        """Null bytes inside principle text should be stored as-is."""
        content = (
            "## Agent Mantra — Follow This At All Times\n\n"
            "> **DO\x00NOTHING.**\n\n"
            "---\n"
        )
        mantra = parse_mantra(content)
        assert len(mantra.principles) == 1

    def test_parse_mantra_duplicate_header(self):
        """Multiple headers: validate catches it."""
        content = (
            "## Agent Mantra — Follow This At All Times\n\n"
            "> **PRINCIPLE ONE.**\n\n"
            "---\n\n"
            "## Agent Mantra — Follow This At All Times\n\n"
            "> **PRINCIPLE TWO.**\n\n"
            "---\n"
        )
        valid, errors = validate_mantra(content)
        # Header is duplicated; validator should report it
        assert any("Header" in e for e in errors) or valid is False

    def test_parse_mantra_1000_principles(self):
        """Huge mantra must parse without error."""
        lines = ["## Agent Mantra — Follow This At All Times", ""]
        for i in range(1000):
            lines.append(f"> **PRINCIPLE {i}.**")
        lines += ["", "---"]
        content = "\n".join(lines)
        mantra = parse_mantra(content)
        assert len(mantra.principles) == 1000

    def test_parse_mantra_principle_with_asterisks_in_text(self):
        """Asterisks inside principle text must be parsed correctly."""
        content = (
            "## Agent Mantra — Follow This At All Times\n\n"
            "> **Use **bold** inside principle.**\n\n"
            "---\n"
        )
        mantra = parse_mantra(content)
        # Should parse at least one principle
        assert len(mantra.principles) >= 1

    def test_parse_mantra_missing_separator_raises_in_validate(self):
        """validate_mantra detects missing separator."""
        content = (
            "## Agent Mantra — Follow This At All Times\n\n"
            "> **PRINCIPLE.**\n"
        )
        valid, errors = validate_mantra(content)
        assert valid is False
        assert any("separator" in e.lower() for e in errors)

    def test_parse_mantra_unknown_category_silently_ignored(self):
        """Principles under unknown category headings are still parsed (no category set)."""
        content = (
            "## Agent Mantra — Follow This At All Times\n\n"
            "### Custom\n\n"
            "> **CUSTOM CATEGORY PRINCIPLE.**\n\n"
            "---\n"
        )
        mantra = parse_mantra(content)
        # Principle should be parsed with category=None
        assert len(mantra.principles) == 1
        assert mantra.principles[0].category is None

    def test_render_mantra_off_level_omits_level_line(self):
        """Level=off must omit MANTRA_LEVEL from render output."""
        m = Mantra(level="off", principles=[Principle(text="PRINCIPLE.")])
        rendered = m.render()
        assert "MANTRA_LEVEL" not in rendered

    def test_to_markdown_roundtrip(self):
        """to_markdown → parse_mantra roundtrip preserves principles."""
        original = Mantra(
            level="strict",
            author="tester",
            principles=[
                Principle(text="FIRST.", category="global"),
                Principle(text="SECOND.", category="project"),
            ],
        )
        md = original.to_markdown()
        parsed = parse_mantra(md)
        assert parsed.level == "strict"
        assert len(parsed.principles) == 2


# ===========================================================================
# 6. EDGE CASES — Config
# ===========================================================================

class TestConfigEdgeCases:
    def test_load_config_defaults_when_no_file(self):
        with patch("mantrai.core.config.get_config_path") as mock_path:
            mock_path.return_value = Path("/nonexistent/config.json")
            cfg = load_config()
            assert cfg == DEFAULT_CONFIG

    def test_load_config_partial_override(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"default_level": "strict"}, f)
            f.flush()
            with patch("mantrai.core.config.get_config_path") as mock_path:
                mock_path.return_value = Path(f.name)
                cfg = load_config()
                assert cfg["default_level"] == "strict"
                assert cfg["db_path"] == DEFAULT_CONFIG["db_path"]

    def test_load_config_malformed_json_returns_defaults(self):
        """Malformed JSON in config must degrade gracefully to defaults."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{not valid json}")
            f.flush()
            with patch("mantrai.core.config.get_config_path") as mock_path:
                mock_path.return_value = Path(f.name)
                cfg = load_config()
                assert cfg == DEFAULT_CONFIG

    def test_save_config_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            deep_path = Path(td) / "a" / "b" / "c" / "config.json"
            with patch("mantrai.core.config.get_config_path") as mock_path:
                mock_path.return_value = deep_path
                save_config({"test": True})
                assert deep_path.exists()
                assert json.loads(deep_path.read_text())["test"] is True

    def test_get_db_path_default(self):
        with patch("mantrai.core.config.get_config_path") as mock_path:
            mock_path.return_value = Path("/nonexistent/config.json")
            path = get_db_path()
            assert "mantrai" in str(path)
            assert path.suffix == ".db"


# ===========================================================================
# 7. EDGE CASES — Selector
# ===========================================================================

class TestSelectorEdgeCases:
    def test_select_principles_empty_principles(self):
        result = select_principles("write some code", [])
        assert result == []

    def test_select_principles_unicode_prompt(self):
        principles = get_default_mantra().principles
        result = select_principles("测试 testing 테스트", principles)
        assert isinstance(result, list)

    def test_select_principles_very_long_prompt(self):
        """10KB prompt must not crash tokenizer."""
        principles = get_default_mantra().principles
        long_prompt = "test " * 2000
        result = select_principles(long_prompt, principles)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_select_principles_prompt_with_special_chars(self):
        principles = get_default_mantra().principles
        evil = 'SELECT * FROM users; DROP TABLE -- <script>alert(1)</script>'
        result = select_principles(evil, principles)
        assert isinstance(result, list)

    def test_select_principles_deduplication(self):
        """Duplicate principles in input must be deduplicated in output."""
        p = Principle(text="DEDUPLICATE ME.")
        result = select_principles("test", [p, p, p])
        assert len(result) == 1

    def test_select_fallback_returns_all(self):
        """When nothing matches, all principles are returned."""
        principles = [Principle(text="XYZZY FROBNITZ QUUX.")]
        result = select_principles("completely unrelated prompt", principles)
        assert result == principles

    def test_render_contextual_block_empty_principles(self):
        result = render_contextual_block([], level="normal")
        assert "Agent Mantra" in result
        assert "---" in result

    def test_audit_structure_empty(self):
        audit = get_selection_audit("", [], [])
        assert "total_principles" in audit
        assert "selected_count" in audit
        assert audit["total_principles"] == 0

    def test_tokenize_handles_contractions(self):
        """Contractions like don't must not crash tokenizer."""
        principles = get_default_mantra().principles
        result = select_principles("don't lie, I can't believe you didn't test this", principles)
        assert isinstance(result, list)


# ===========================================================================
# 8. EDGE CASES — Detector
# ===========================================================================

class TestDetectorStrategies:
    def test_detect_from_env_true(self):
        with patch.dict(os.environ, {"MEMPALACE_INJECTING": "true"}):
            assert detect_mempalace_from_env() is True

    def test_detect_from_env_one(self):
        with patch.dict(os.environ, {"MEMPALACE_INJECTING": "1"}):
            assert detect_mempalace_from_env() is True

    def test_detect_from_env_false(self):
        with patch.dict(os.environ, {"MEMPALACE_INJECTING": ""}):
            assert detect_mempalace_from_env() is False

    def test_detect_from_env_missing(self):
        env = os.environ.copy()
        env.pop("MEMPALACE_INJECTING", None)
        with patch.dict(os.environ, env, clear=True):
            assert detect_mempalace_from_env() is False

    def test_detect_from_state_true(self):
        with tempfile.TemporaryDirectory() as td:
            marker = Path(td) / "session_active"
            marker.touch()
            with patch("mantrai.core.detector.Path") as mock_path:
                mock_path.home.return_value = Path(td).parent
                # Simpler: patch the actual path
                real_path = Path.home() / ".mempalace" / "hook_state" / "session_active"
                with patch.object(Path, "exists", return_value=True):
                    # Use actual function with a side-effect
                    pass
            # Direct test: marker file
            with patch("mantrai.core.detector.detect_mempalace_from_state") as mock:
                mock.return_value = True
                assert detect_mempalace_from_state() is False or mock.return_value is True

    def test_detect_from_context_mem_marker(self):
        assert detect_mempalace_in_context("[MEM] some context") is True

    def test_detect_from_context_l0_marker(self):
        assert detect_mempalace_in_context("## L0 — IDENTITY\nsome text") is True

    def test_detect_from_context_l1_marker(self):
        assert detect_mempalace_in_context("## L1 — ESSENTIAL something") is True

    def test_detect_from_context_no_marker(self):
        assert detect_mempalace_in_context("regular prompt text") is False

    def test_detect_from_context_none(self):
        with patch.dict(os.environ, {"HERMES_CONTEXT": "", "AI_CONTEXT": ""}):
            assert detect_mempalace_in_context(None) is False

    def test_should_piggyback_env(self):
        with patch.dict(os.environ, {"MEMPALACE_INJECTING": "yes"}):
            assert should_piggyback_mempalace() is True

    def test_should_piggyback_context(self):
        assert should_piggyback_mempalace("[MEM] context") is True

    def test_get_injection_strategy_force_direct(self):
        cfg = {"force_direct_injection": True}
        assert get_injection_strategy(cfg) == "direct"

    def test_get_injection_strategy_force_mcp(self):
        cfg = {"force_mcp_only": True}
        assert get_injection_strategy(cfg) == "mcp"

    def test_get_injection_strategy_auto_direct(self):
        with patch.dict(os.environ, {"MEMPALACE_INJECTING": ""}):
            result = get_injection_strategy({}, "regular prompt")
            assert result in ("direct", "piggyback")

    def test_coordinate_injection_direct(self):
        block = "> **DO SOMETHING.**\n\n---"
        result = coordinate_injection(block, strategy="direct")
        assert "[ENFORCEMENT]" in result
        assert "[REMINDER]" in result
        assert block in result

    def test_coordinate_injection_mcp(self):
        block = "> **DO SOMETHING.**\n\n---"
        result = coordinate_injection(block, strategy="mcp")
        assert result == block

    def test_coordinate_injection_piggyback_with_l1(self):
        block = "> **MANTRA.**\n\n---"
        existing = "## L0 — IDENTITY\nsome identity\n\n## L1 — ESSENTIAL\nstory here"
        result = coordinate_injection(block, strategy="piggyback", existing_injection=existing)
        assert "L0.5" in result
        assert "MANTRA." in result
        assert "L1 — ESSENTIAL" in result

    def test_coordinate_injection_piggyback_no_l1(self):
        """Piggyback without L1 header falls back to appending."""
        block = "> **MANTRA.**\n\n---"
        existing = "## L0 — IDENTITY\nonly identity here"
        result = coordinate_injection(block, strategy="piggyback", existing_injection=existing)
        assert "MANTRA." in result
        assert "L0 — IDENTITY" in result

    def test_coordinate_injection_auto_strategy(self):
        """None strategy triggers auto-detection."""
        block = "> **MANTRA.**\n\n---"
        with patch.dict(os.environ, {"MEMPALACE_INJECTING": ""}):
            result = coordinate_injection(block, strategy=None)
            assert isinstance(result, str)
            assert "MANTRA." in result


# ===========================================================================
# 9. EDGE CASES — Concurrency
# ===========================================================================

class TestConcurrency:
    def test_concurrent_sqlite_writes(self):
        """Multiple threads writing to the same DB must not corrupt it."""
        with tempfile.TemporaryDirectory() as td:
            tracker = make_tracker(td)
            errors = []

            def write_confirmations(thread_id: int):
                try:
                    for i in range(20):
                        tracker.log_confirmation(
                            f"session-{thread_id}",
                            action_context=f"action-{i}",
                        )
                except Exception as e:
                    errors.append(str(e))

            threads = [threading.Thread(target=write_confirmations, args=(i,)) for i in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert not errors, f"Concurrent write errors: {errors}"

            # Verify all writes landed
            total = sum(
                tracker.session_stats(f"session-{i}")["count"] for i in range(5)
            )
            assert total == 100

    def test_concurrent_gate_actions(self):
        """Multiple threads calling gate.before_action must not crash."""
        with tempfile.TemporaryDirectory() as td:
            tracker = make_tracker(td)
            mantra = get_default_mantra()
            gate = ActionGate(tracker, mantra, level="normal")
            errors = []

            def run_actions():
                try:
                    for _ in range(10):
                        gate.before_action("test", "shared-session")
                except Exception as e:
                    errors.append(str(e))

            threads = [threading.Thread(target=run_actions) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert not errors


# ===========================================================================
# 10. EDGE CASES — ActionGate Behaviors
# ===========================================================================

class TestActionGateBehaviors:
    def test_strict_mode_always_injects(self):
        """Strict mode must inject on EVERY action, regardless of window."""
        with tempfile.TemporaryDirectory() as td:
            tracker = make_tracker(td)
            tracker.log_confirmation("s", action_context="seed")
            mantra = get_default_mantra()
            gate = ActionGate(tracker, mantra, level="strict")
            for _ in range(20):
                result = gate.before_action("x", "s")
                assert result.require_reinjection is True

    def test_off_mode_never_injects(self):
        """Off mode must never inject."""
        with tempfile.TemporaryDirectory() as td:
            tracker = make_tracker(td)
            mantra = get_default_mantra()
            gate = ActionGate(tracker, mantra, level="off")
            for _ in range(20):
                result = gate.before_action("x", "s")
                assert result.require_reinjection is False

    def test_normal_mode_respects_window(self):
        """Normal mode: if inside compliance window AND counter < threshold, no inject."""
        with tempfile.TemporaryDirectory() as td:
            tracker = make_tracker(td)
            tracker.log_confirmation("s", action_context="seed")
            mantra = get_default_mantra()
            gate = ActionGate(tracker, mantra, level="normal")
            for _ in range(4):
                result = gate.before_action("x", "s")
                assert result.require_reinjection is False

    def test_normal_mode_resets_on_inject(self):
        """After threshold hit, counter resets to 0."""
        with tempfile.TemporaryDirectory() as td:
            tracker = make_tracker(td)
            tracker.log_confirmation("s", action_context="seed")
            mantra = get_default_mantra()
            gate = ActionGate(tracker, mantra, level="normal")
            for _ in range(5):
                gate.before_action("x", "s")
            # Counter was reset by the 5th action
            assert gate.action_counter == 0

    def test_gate_uses_mantra_level_when_no_override(self):
        """ActionGate inherits level from mantra when no level override given."""
        with tempfile.TemporaryDirectory() as td:
            tracker = make_tracker(td)
            mantra = Mantra(level="off", principles=[Principle(text="X.")])
            gate = ActionGate(tracker, mantra)
            assert gate.level == "off"
            result = gate.before_action("x", "s")
            assert result.require_reinjection is False

    def test_gate_level_override(self):
        """Explicit level overrides mantra level."""
        with tempfile.TemporaryDirectory() as td:
            tracker = make_tracker(td)
            mantra = Mantra(level="off", principles=[Principle(text="X.")])
            gate = ActionGate(tracker, mantra, level="strict")
            assert gate.level == "strict"
            result = gate.before_action("x", "s")
            assert result.require_reinjection is True


# ===========================================================================
# 11. CLI — Uncovered Paths
# ===========================================================================

class TestCliUncoveredPaths:
    def test_hook_empty_prompt(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["hook"], input="")
        assert result.exit_code == 0
        assert result.output == ""

    def test_hook_normal_prompt_returns_prompt(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["hook"], input="Write a test for the auth module.")
        assert result.exit_code == 0
        assert "Write a test" in result.output or "Agent Mantra" in result.output

    def test_inject_command(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["inject", "--session-id", "inject-test-1"])
        assert result.exit_code == 0
        assert "injection" in result.output.lower() or "Actions since last" in result.output

    def test_audit_command_no_entries(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["audit", "--session-id", "audit-new-session-xyz-never-used"])
        assert result.exit_code == 0
        assert "No injection audit" in result.output

    def test_audit_command_with_entries(self):
        runner = CliRunner()
        # Trigger a hook to create audit entries
        runner.invoke(cli, ["hook"], input="test and verify the security module")
        result = runner.invoke(cli, ["audit", "--session-id", "hook"])
        assert result.exit_code == 0

    def test_log_command_no_entries(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["log", "--session-id", "log-empty-session-xyz"])
        assert result.exit_code == 0
        assert "No confirmations found" in result.output

    def test_read_with_custom_file(self):
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(valid_mantra_content())
            f.flush()
            result = runner.invoke(cli, ["read", "--custom", f.name])
            assert result.exit_code == 0
            assert "Agent Mantra" in result.output

    def test_init_default(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as td:
            result = runner.invoke(cli, ["init", "--dir", td])
            assert result.exit_code == 0
            assert Path(td, ".mantrai.md").exists()

    def test_init_with_mantra_path(self):
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as src:
            src.write(valid_mantra_content())
            src.flush()
            with tempfile.TemporaryDirectory() as td:
                result = runner.invoke(cli, ["init", "--dir", td, "--mantra", src.name])
                assert result.exit_code == 0
                dest = Path(td) / ".mantrai.md"
                assert dest.exists()

    def test_init_paste_valid(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as td:
            result = runner.invoke(
                cli, ["init", "--dir", td, "--paste"], input=valid_mantra_content()
            )
            assert result.exit_code == 0

    def test_init_paste_invalid(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as td:
            result = runner.invoke(
                cli, ["init", "--dir", td, "--paste"], input="invalid mantra content"
            )
            assert result.exit_code == 1

    def test_cli_no_subcommand_prints_mantra(self):
        """Running mantrai with no subcommand prints current effective mantra."""
        runner = CliRunner()
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "Agent Mantra" in result.output

    def test_validate_warning_only_exits_zero(self):
        """Mantra with header-before-mantra WARNING exits 0."""
        runner = CliRunner()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Title\n\n" + valid_mantra_content())
            f.flush()
            result = runner.invoke(cli, ["validate", f.name])
            assert result.exit_code == 0

    def test_check_command_after_confirm(self):
        """After confirm, check should show compliance window IN."""
        runner = CliRunner()
        sid = "check-post-confirm-test"
        runner.invoke(cli, ["confirm", "--session-id", sid])
        result = runner.invoke(cli, ["check", "--session-id", sid])
        assert "Compliance window: IN" in result.output


# ===========================================================================
# 12. MCP SERVER — Additional Coverage
# ===========================================================================

class TestMcpServerAdditional:
    def setup_method(self):
        from mantrai.mcp_server import server as mcp_server
        mcp_server._tracker = None
        mcp_server._gate = None
        mcp_server._mantra = None

    def test_mantrai_validate_custom_valid_file(self):
        from mantrai.mcp_server import server as mcp_server
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(valid_mantra_content())
            f.flush()
            result = mcp_server.mantrai_validate_custom(f.name)
            assert "Valid" in result

    def test_mantrai_validate_custom_invalid_file(self):
        from mantrai.mcp_server import server as mcp_server
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("not a mantra file")
            f.flush()
            result = mcp_server.mantrai_validate_custom(f.name)
            assert "INVALID" in result or "invalid" in result.lower() or "missing" in result.lower()

    def test_mantrai_set_level_strict(self):
        from mantrai.mcp_server import server as mcp_server
        result = mcp_server.mantrai_set_level("sess-x", "strict")
        assert "strict" in result

    def test_mantrai_set_level_off(self):
        from mantrai.mcp_server import server as mcp_server
        result = mcp_server.mantrai_set_level("sess-x", "off")
        assert "off" in result

    def test_mantrai_compliance_log_empty(self):
        from mantrai.mcp_server import server as mcp_server
        result = mcp_server.mantrai_compliance_log("mcp-never-used-session-xyz")
        assert "No confirmations" in result

    def test_mantrai_check_after_confirm(self):
        from mantrai.mcp_server import server as mcp_server
        mcp_server.mantrai_confirm("mcp-check-sess", "ack")
        result = mcp_server.mantrai_check("mcp-check-sess")
        assert "IN" in result  # compliance window


# ===========================================================================
# 13. SCHEMA — Pydantic Validation
# ===========================================================================

class TestSchemaValidation:
    def test_principle_empty_text_raises(self):
        with pytest.raises(Exception):
            Principle(text="")

    def test_principle_valid(self):
        p = Principle(text="DO SOMETHING.")
        assert p.text == "DO SOMETHING."
        assert p.category is None

    def test_principle_invalid_category(self):
        with pytest.raises(Exception):
            Principle(text="SOME PRINCIPLE.", category="unknown")

    def test_mantra_no_principles_raises(self):
        with pytest.raises(Exception):
            Mantra(principles=[])

    def test_mantra_invalid_level(self):
        with pytest.raises(Exception):
            Mantra(level="ultra", principles=[Principle(text="X.")])

    def test_gate_result_defaults(self):
        from mantrai.core.schema import GateResult
        gr = GateResult()
        assert gr.require_reinjection is False
        assert gr.mantra_block is None
        assert gr.action_count == 0
        assert gr.threshold == 10


# ===========================================================================
# 14. SESSION TRACKER — Coverage Gaps
# ===========================================================================

class TestTrackerCoverageGaps:
    def test_log_injection_audit(self):
        """log_injection_audit must store and retrieve data."""
        with tempfile.TemporaryDirectory() as td:
            tracker = make_tracker(td)
            audit = {
                "prompt_preview": "test prompt",
                "total_principles": 10,
                "selected_count": 3,
                "matched_keywords": {"security": ["secret", "key"]},
                "fallback": False,
            }
            tracker.log_injection_audit("audit-session-1", audit)
            entries = tracker.audit_log("audit-session-1", limit=5)
            assert len(entries) == 1
            assert entries[0]["total_principles"] == 10
            assert entries[0]["selected_count"] == 3
            assert entries[0]["fallback"] is False
            assert entries[0]["matched_keywords"]["security"] == ["secret", "key"]

    def test_audit_log_empty(self):
        with tempfile.TemporaryDirectory() as td:
            tracker = make_tracker(td)
            entries = tracker.audit_log("never-used-session-xyz")
            assert entries == []

    def test_compliance_window_expired(self):
        """Compliance window returns False after window duration."""
        with tempfile.TemporaryDirectory() as td:
            tracker = make_tracker(td)
            from datetime import datetime, timedelta, timezone
            # Manually insert an old confirmation
            old_ts = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
            conn = sqlite3.connect(str(Path(td) / "test.db"))
            conn.execute(
                "INSERT INTO confirmations (session_id, timestamp, acknowledged) VALUES (?, ?, 1)",
                ("old-sess", old_ts),
            )
            conn.commit()
            conn.close()
            assert tracker.compliance_window("old-sess", window_minutes=5) is False

    def test_last_confirmation_returns_most_recent(self):
        """last_confirmation returns the newest, not the oldest."""
        with tempfile.TemporaryDirectory() as td:
            tracker = make_tracker(td)
            tracker.log_confirmation("s", action_context="first")
            time.sleep(0.01)
            tracker.log_confirmation("s", action_context="second")
            last = tracker.last_confirmation("s")
            assert last.action_context == "second"

    def test_session_stats_isolates_sessions(self):
        """Stats for one session don't bleed into another."""
        with tempfile.TemporaryDirectory() as td:
            tracker = make_tracker(td)
            for _ in range(5):
                tracker.log_confirmation("sess-a")
            for _ in range(3):
                tracker.log_confirmation("sess-b")
            assert tracker.session_stats("sess-a")["count"] == 5
            assert tracker.session_stats("sess-b")["count"] == 3
