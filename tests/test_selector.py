from __future__ import annotations

import pytest

from mantrai.core.schema import Principle
from mantrai.core.selector import (
    get_selection_audit,
    render_contextual_block,
    select_principles,
)


class TestSelectPrinciples:
    def test_selects_relevant_principles(self):
        principles = [
            Principle(text="ABSOLUTELY NO SIMULATIONS", category="global"),
            Principle(text="Never lie or trick", category="global"),
            Principle(text="Read before you write", category="global"),
            Principle(text="Security over convenience", category="global"),
        ]
        prompt = "write a test that mocks the database"
        selected = select_principles(prompt, principles)
        texts = [p.text for p in selected]
        assert "ABSOLUTELY NO SIMULATIONS" in texts
        assert "Read before you write" in texts

    def test_fallback_when_no_match(self):
        principles = [
            Principle(text="Stop one deployment", category="global"),
            Principle(text="Update ALL documentation", category="global"),
        ]
        prompt = "hello how are you"
        selected = select_principles(prompt, principles)
        assert len(selected) == 2  # fallback returns all

    def test_empty_prompt_returns_all(self):
        principles = [Principle(text="Test principle", category="global")]
        assert select_principles("", principles) == principles
        assert select_principles("   ", principles) == principles


class TestRenderContextualBlock:
    def test_renders_selected_principles(self):
        principles = [
            Principle(text="Read before you write", category="global"),
            Principle(text="Security over convenience", category="global"),
        ]
        block = render_contextual_block(principles, level="strict")
        assert "## Agent Mantra — Contextual Reminders" in block
        assert "Read before you write" in block
        assert "Security over convenience" in block
        assert "MANTRA_LEVEL=strict" in block
        assert "---" in block

    def test_off_level_omits_level_line(self):
        principles = [Principle(text="Test", category="global")]
        block = render_contextual_block(principles, level="off")
        assert "MANTRA_LEVEL" not in block


class TestGetSelectionAudit:
    def test_audit_structure(self):
        principles = [
            Principle(text="Read before you write", category="global"),
            Principle(text="Security over convenience", category="global"),
        ]
        prompt = "write a secure function"
        selected = select_principles(prompt, principles)
        audit = get_selection_audit(prompt, principles, selected)
        assert audit["total_principles"] == 2
        assert audit["selected_count"] >= 1
        assert "prompt_preview" in audit
        assert isinstance(audit["fallback"], bool)
