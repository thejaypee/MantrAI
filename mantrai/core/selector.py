"""
Contextual principle selector — match prompt intent to relevant mantra principles.

No enforcement. Just injection + audit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from mantrai.core.schema import Principle


# Keyword → principle text prefix mapping
# Each principle is matched by a set of keywords that indicate relevance.
# A principle is included if ANY of its keywords appear in the prompt.
# Principles with no keywords (None) are always included as universal rules.
# The key is a lowercase prefix of the principle text for robust matching.
KEYWORD_MAP: dict[str, set[str] | None] = {
    "absolutely no simulations": {"simulation", "test result", "fabricate", "mock", "fake", "output", "command output", "api response", "run it"},
    "never lie or trick": {"lie", "trick", "bluff", "uncertain", "don't know", "guess", "assume", "pretend"},
    "no changes that are not requested": {"refactor", "cleanup", "clean up", "while i'm here", "optimize", "improve", "rename", "restructure", "scope", "abstraction"},
    "read before you write": {"edit", "write", "modify", "change", "create", "update", "fix", "open file", "read file", "file content", "stale"},
    "thoroughly test before claiming success": {"test", "pass", "green", "verify", "check", "stderr", "exit code", "pytest", "assert"},
    "stop one deployment before starting another": {"deploy", "start server", "port", "launch", "run server", "zombie", "process", "stack", "clean up"},
    "update all documentation": {"doc", "readme", "changelog", "comment", "documentation", "update doc"},
    "security over convenience": {"secret", "password", "key", "token", "auth", "verify", "disable", "flag", "hardcode", "injection", "vulnerability", "security"},
    "plan first": {"plan", "architecture", "design", "approach", "strategy", "roadmap", "plan mode"},
    "/init before acting": {"init", "setup", "configure", "install", "first time", "read document"},
    "make plan and checklist": {"checklist", "todo", "steps", "organize", "plan first"},
    "confirm all checklist items with human": {"done", "complete", "finished", "ready", "confirm", "acknowledge"},
    "/build mode": {"build", "implement", "code", "develop", "write code", "build mode"},
    "fix everything always": {"fix", "broken", "error", "fail", "lint", "todo", "broken test"},
    "interactive human demo": {"show", "demo", "preview", "visual", "ui", "screenshot", "interactive"},
    "wait for confirmation task is accomplished": {"wait", "confirmation", "task accomplished", "close task"},
    "treat repositories as modules": {"repo", "vendor", "dependency", "import", "module", "boundary"},
    "follow the original repository's documentation": {"docs", "readme", "guide", "tutorial", "original documentation"},
    "build adapters or use .env files": {"config", "env", "adapter", "boundary", "integration", ".env", "environment"},
    "file to mempalace": {"memory", "save", "document", "context", "record", "mempalace", "diary", "drawer"},
}


def _tokenize(text: str) -> set[str]:
    """Lowercase, extract words, stems, and common phrases."""
    lower = text.lower()
    # Extract words
    words = set(re.findall(r"[a-z]+(?:['][a-z]+)?", lower))
    # Add stemmed forms (simple suffix stripping)
    stems = set()
    for w in words:
        if w.endswith(("ing", "ed", "s", "es", "ies")):
            stems.add(w.rstrip("ies") + "y" if w.endswith("ies") else w.rstrip("s"))
            stems.add(w.rstrip("ing"))
            stems.add(w.rstrip("ed"))
    # Extract common 2-word phrases
    tokens = lower.split()
    phrases = {f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens) - 1)}
    return words | stems | phrases


def _get_keywords_for_principle(principle: Principle) -> set[str] | None:
    """Find keywords for a principle by matching its text prefix (either direction)."""
    lower = principle.text.lower()
    for prefix, keywords in KEYWORD_MAP.items():
        if lower.startswith(prefix) or prefix.startswith(lower):
            return keywords
    return None


def select_principles(prompt_text: str, principles: list[Principle]) -> list[Principle]:
    """
    Select principles relevant to the prompt intent.

    Returns a deduplicated list of principles whose keywords match the prompt.
    If no keywords match, returns all principles (fallback to full mantra).
    """
    if not prompt_text or not principles:
        return principles

    tokens = _tokenize(prompt_text)
    matched: list[Principle] = []
    seen_texts: set[str] = set()

    for principle in principles:
        keywords = _get_keywords_for_principle(principle)
        if keywords is None:
            # No keywords = universal, always include
            if principle.text not in seen_texts:
                matched.append(principle)
                seen_texts.add(principle.text)
            continue

        if tokens & keywords:
            if principle.text not in seen_texts:
                matched.append(principle)
                seen_texts.add(principle.text)

    # Fallback: if nothing matched, return all principles
    if not matched:
        return principles

    return matched


def render_contextual_block(
    principles: list[Principle],
    level: str = "strict",
    matched_indices: Optional[list[int]] = None,
) -> str:
    """
    Render a contextual mantra block with only the selected principles.

    Args:
        principles: The selected principles to inject
        level: Mantra level (strict, normal, off)
        matched_indices: Optional list of which indices were matched (for audit logging)

    Returns:
        Formatted mantra block for injection
    """
    lines = ["## Agent Mantra — Contextual Reminders", ""]

    for p in principles:
        lines.append(f"> **{p.text}**")

    if level != "off":
        lines.append("")
        lines.append(f"> **MANTRA_LEVEL={level}.**")

    lines.append("")
    lines.append("---")

    return "\n".join(lines)


def get_selection_audit(
    prompt_text: str,
    all_principles: list[Principle],
    selected: list[Principle],
) -> dict:
    """Build an audit record of what was selected and why."""
    tokens = _tokenize(prompt_text)
    matched_keywords: dict[str, list[str]] = {}

    for principle in all_principles:
        if principle not in selected:
            continue
        keywords = _get_keywords_for_principle(principle)
        if not keywords:
            continue
        hits = sorted(tokens & keywords)
        if hits:
            matched_keywords[principle.text[:60]] = hits

    return {
        "prompt_preview": prompt_text[:200],
        "total_principles": len(all_principles),
        "selected_count": len(selected),
        "matched_keywords": matched_keywords,
        "fallback": len(selected) == len(all_principles),
    }
