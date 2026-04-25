from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from mantrai.core.mantra import (
    DEFAULT_HEADER,
    get_default_mantra,
    load_mantra,
    parse_mantra,
    render_mantra_block,
    validate_mantra,
)
from mantrai.core.schema import Mantra, Principle


class TestLoadDefaultMantra:
    def test_load_default_mantra(self):
        mantra = get_default_mantra()
        assert isinstance(mantra, Mantra)
        assert len(mantra.principles) >= 7
        assert mantra.header == DEFAULT_HEADER
        assert mantra.level == "normal"

    def test_load_default_from_path(self):
        mantra = load_mantra()
        assert isinstance(mantra, Mantra)
        assert len(mantra.principles) >= 7


class TestLoadCustomMantra:
    def test_load_custom_with_frontmatter(self):
        content = """**Level:** `strict`
**Author:** testuser

## Agent Mantra — Follow This At All Times

> **ALWAYS WRITE TESTS FIRST.**
> **NEVER SKIP CODE REVIEW.**

---
"""
        mantra = parse_mantra(content)
        assert mantra.level == "strict"
        assert mantra.author == "testuser"
        assert len(mantra.principles) == 2
        assert mantra.principles[0].text == "ALWAYS WRITE TESTS FIRST."

    def test_load_custom_no_frontmatter(self):
        content = """## Agent Mantra — Follow This At All Times

> **PRINCIPLE ONE.**
> **PRINCIPLE TWO.**

---
"""
        mantra = parse_mantra(content)
        assert mantra.level == "normal"
        assert mantra.author is None
        assert len(mantra.principles) == 2


class TestValidateMantra:
    def test_validate_valid_mantra(self):
        content = """## Agent Mantra — Follow This At All Times

> **MAKE NO MISTAKES.**
> **FIX EVERYTHING ALWAYS.**

---
"""
        valid, errors = validate_mantra(content)
        assert valid is True
        assert not errors or all("WARNING" in e for e in errors)

    def test_validate_missing_header(self):
        content = "> **PRINCIPLE.**\n\n---\n"
        valid, errors = validate_mantra(content)
        assert valid is False
        assert any("Missing required mantra header" in e for e in errors)

    def test_validate_no_principles(self):
        content = """## Agent Mantra — Follow This At All Times

---
"""
        valid, errors = validate_mantra(content)
        assert valid is False
        assert any("No principles found" in e for e in errors)

    def test_validate_missing_separator(self):
        content = """## Agent Mantra — Follow This At All Times

> **PRINCIPLE.**
"""
        valid, errors = validate_mantra(content)
        assert valid is False
        assert any("Missing '---' separator" in e for e in errors)

    def test_validate_header_before_mantra(self):
        content = """# Title

## Agent Mantra — Follow This At All Times

> **PRINCIPLE.**

---
"""
        valid, errors = validate_mantra(content)
        # Should pass with warning
        assert any("WARNING" in e for e in errors)


class TestRenderMantra:
    def test_render_mantra_block(self):
        mantra = Mantra(
            level="normal",
            principles=[Principle(text="TEST PRINCIPLE.")],
        )
        block = render_mantra_block(mantra)
        assert DEFAULT_HEADER in block
        assert "> **TEST PRINCIPLE.**" in block
        assert "---" in block

    def test_render_includes_level(self):
        mantra = Mantra(
            level="strict",
            principles=[Principle(text="TEST.")],
        )
        block = render_mantra_block(mantra)
        assert "MANTRA_LEVEL=strict" in block
