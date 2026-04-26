"""
MemPalace detector — Check if MemPalace is injecting this session.

Model/agent agnostic. Uses multiple detection strategies.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional


def detect_mempalace_from_env() -> bool:
    """Check if MemPalace has signaled via environment variable."""
    return os.getenv("MEMPALACE_INJECTING", "").lower() in ("true", "1", "yes")


def detect_mempalace_from_state() -> bool:
    """Check if MemPalace session state file exists."""
    state_marker = Path.home() / ".mempalace" / "hook_state" / "session_active"
    return state_marker.exists()


def detect_mempalace_in_context(context: Optional[str] = None) -> bool:
    """Check if current context contains MemPalace markers."""
    if context is None:
        context = _get_injected_context()
    
    if not context:
        return False
    
    # MemPalace markers found in injected context
    markers = [
        r"\[MEM\]",           # Direct marker
        r"## L0 — IDENTITY",   # L0 layer header
        r"## L1 — ESSENTIAL",  # L1 layer header
    ]
    
    return any(re.search(marker, context) for marker in markers)


def _get_injected_context() -> Optional[str]:
    """Get current pre-injected context from environment or session."""
    # Check Hermes/Axiom specific context injection
    ctx = os.getenv("HERMES_CONTEXT", "")
    if ctx:
        return ctx
    
    # Check generic AI context variable
    ctx = os.getenv("AI_CONTEXT", "")
    if ctx:
        return ctx
    
    return None


def should_piggyback_mempalace(context: Optional[str] = None) -> bool:
    """
    Determine if MantrAI should piggyback on MemPalace injection.
    
    Returns True if MemPalace detected through any strategy.
    """
    # Strategy priority: explicit env > state file > context parsing
    
    if detect_mempalace_from_env():
        return True
    
    if detect_mempalace_from_state():
        return True
    
    if detect_mempalace_in_context(context):
        return True
    
    return False


def get_injection_strategy(config: Optional[dict] = None, context: Optional[str] = None) -> str:
    """
    Determine injection strategy based on environment.
    
    Args:
        config: MantrAI configuration dict
        context: The current prompt/context being processed (for detecting MemPalace markers)
    
    Returns:
        "piggyback" — MemPalace detected, append to its injection
        "direct" — Inject directly via hook
        "mcp" — Fallback to MCP tools only
    """
    cfg = config or {}
    
    # Manual override
    if cfg.get("force_direct_injection"):
        return "direct"
    
    if cfg.get("force_mcp_only"):
        return "mcp"
    
    # Auto-detect using context (stdin/prompt content)
    if should_piggyback_mempalace(context):
        return "piggyback"
    
    return "direct"


def coordinate_injection(
    mantra_block: str,
    strategy: Optional[str] = None,
    existing_injection: Optional[str] = None,
) -> str:
    """
    Coordinate mantra injection based on detected strategy.
    
    Args:
        mantra_block: The mantra text to inject
        strategy: "piggyback", "direct", "mcp", or None for auto
        existing_injection: If piggybacking, the existing context being injected
    
    Returns:
        Final injection text
    """
    if strategy is None:
        strategy = get_injection_strategy()
    
    if strategy == "piggyback" and existing_injection:
        # Insert mantra between L0 (identity) and L1 (essential story)
        # Pattern: Find L1 header and insert before it
        l1_match = re.search(r"(## L1 — .*)$", existing_injection, re.MULTILINE)
        if l1_match:
            pos = l1_match.start()
            return (
                existing_injection[:pos]
                + f"## L0.5 — Mantra\n\n{mantra_block}\n\n"
                + existing_injection[pos:]
            )
        # Fallback: append to what's there
        return f"{existing_injection}\n\n## Mantra\n\n{mantra_block}"
    
    elif strategy == "direct":
        # Full standalone injection with enforcement
        enforcement = (
            "\n[ENFORCEMENT] BEFORE READING OR WRITING ANY FILE, "
            "RE-READ THE MANTRA ABOVE AND CALL mantrai_confirm. "
            "DO NOT PROCEED WITH FILE OPERATIONS UNTIL ACKNOWLEDGED.[/ENFORCEMENT]\n"
        )
        trailing = (
            "\n\n[REMINDER] AFTER COMPLETING THIS TASK, UPDATE MEMORY: "
            "1) mempalace_diary_write — session summary, 2) mempalace_add_drawer — verbatim quotes/decisions, "
            "3) mempalace_kg_add — entity relationships. DO NOT SKIP.[/REMINDER]"
        )
        return f"{mantra_block}\n{enforcement}\n{trailing}"
    
    else:  # mcp
        # MCP mode: just return mantra, client handles rest
        return mantra_block
