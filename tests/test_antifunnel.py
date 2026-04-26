from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from mantrai.session.gate import ActionGate
from mantrai.session.injector import MantraInjector
from mantrai.session.tracker import SessionTracker
from mantrai.core.mantra import get_default_mantra
from mantrai.core.schema import Mantra, Principle


class TestSessionTracker:
    def test_session_log_confirmation(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "test.db"
            tracker = SessionTracker(db_path=db)
            c = tracker.log_confirmation("sess-1", agent_id="a1", action_context="test")
            assert c.session_id == "sess-1"
            assert c.agent_id == "a1"
            assert c.action_context == "test"
            assert c.acknowledged is True

    def test_session_last_confirmation(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "test.db"
            tracker = SessionTracker(db_path=db)
            tracker.log_confirmation("sess-1", action_context="first")
            tracker.log_confirmation("sess-1", action_context="second")
            last = tracker.last_confirmation("sess-1")
            assert last is not None
            assert last.action_context == "second"

    def test_session_compliance_window(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "test.db"
            tracker = SessionTracker(db_path=db)
            assert tracker.compliance_window("sess-1", 5) is False
            tracker.log_confirmation("sess-1", action_context="ack")
            assert tracker.compliance_window("sess-1", 5) is True

    def test_session_stats(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "test.db"
            tracker = SessionTracker(db_path=db)
            stats = tracker.session_stats("sess-1")
            assert stats["count"] == 0
            tracker.log_confirmation("sess-1", action_context="ack")
            tracker.log_confirmation("sess-1", action_context="ack2")
            stats = tracker.session_stats("sess-1")
            assert stats["count"] == 2
            assert stats["first"] is not None
            assert stats["last"] is not None

    def test_compliance_log(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "test.db"
            tracker = SessionTracker(db_path=db)
            tracker.log_confirmation("sess-1", action_context="ack1")
            tracker.log_confirmation("sess-1", action_context="ack2")
            logs = tracker.compliance_log("sess-1", limit=10)
            assert len(logs) == 2


class TestActionGate:
    def test_gate_normal_inject_every_n(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "test.db"
            tracker = SessionTracker(db_path=db)
            # Pre-confirm so compliance window is satisfied
            tracker.log_confirmation("sess-1", action_context="setup")
            mantra = get_default_mantra()
            gate = ActionGate(tracker, mantra, level="normal")
            assert gate.threshold == 5

            # First 4 actions should not require injection
            for _ in range(4):
                result = gate.before_action("edit", "sess-1")
                assert result.require_reinjection is False

            # 5th action should require injection
            result = gate.before_action("edit", "sess-1")
            assert result.require_reinjection is True
            assert result.mantra_block is not None

    def test_gate_strict_inject_every_action(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "test.db"
            tracker = SessionTracker(db_path=db)
            mantra = get_default_mantra()
            gate = ActionGate(tracker, mantra, level="strict")
            assert gate.threshold == 1

            for _ in range(3):
                result = gate.before_action("edit", "sess-1")
                assert result.require_reinjection is True
                assert result.mantra_block is not None

    def test_gate_off_no_inject(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "test.db"
            tracker = SessionTracker(db_path=db)
            mantra = get_default_mantra()
            gate = ActionGate(tracker, mantra, level="off")

            for _ in range(10):
                result = gate.before_action("edit", "sess-1")
                assert result.require_reinjection is False

    def test_gate_action_counter_increments(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "test.db"
            tracker = SessionTracker(db_path=db)
            tracker.log_confirmation("sess-1", action_context="setup")
            mantra = get_default_mantra()
            gate = ActionGate(tracker, mantra, level="normal")

            result = gate.before_action("edit", "sess-1")
            assert result.action_count == 1
            result = gate.before_action("edit", "sess-1")
            assert result.action_count == 2

    def test_gate_reset_counter(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "test.db"
            tracker = SessionTracker(db_path=db)
            mantra = get_default_mantra()
            gate = ActionGate(tracker, mantra, level="normal")

            gate.before_action("edit", "sess-1")
            gate.before_action("edit", "sess-1")
            gate.reset_counter()
            assert gate.action_counter == 0


class TestMantraInjector:
    def test_injector_render_block(self):
        mantra = Mantra(principles=[Principle(text="TEST.")])
        injector = MantraInjector(mantra)
        block = injector.inject()
        assert "> **TEST.**" in block

    def test_injector_includes_level(self):
        mantra = Mantra(level="strict", principles=[Principle(text="TEST.")])
        injector = MantraInjector(mantra)
        block = injector.inject_with_level("strict")
        assert "MANTRA_LEVEL=strict" in block
