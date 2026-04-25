from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

from mantrai.antifunnel.gate import ActionGate
from mantrai.antifunnel.session import SessionTracker
from mantrai.core.config import load_config
from mantrai.core.mantra import load_mantra, validate_mantra
from mantrai.core.schema import Mantra

mcp = FastMCP("mantrai")

# Global state (single-session for stdio mode)
_tracker: Optional[SessionTracker] = None
_gate: Optional[ActionGate] = None
_mantra: Optional[Mantra] = None


def _get_tracker() -> SessionTracker:
    global _tracker
    if _tracker is None:
        cfg = load_config()
        from mantrai.core.config import get_db_path

        _tracker = SessionTracker(db_path=get_db_path(cfg))
    return _tracker


def _get_mantra() -> Mantra:
    global _mantra
    if _mantra is None:
        cfg = load_config()
        custom_path = cfg.get("mantra_path")
        if custom_path:
            _mantra = load_mantra(Path(custom_path))
        else:
            _mantra = load_mantra()
    return _mantra


def _get_gate(level: Optional[str] = None) -> ActionGate:
    global _gate
    if _gate is None:
        _gate = ActionGate(
            tracker=_get_tracker(),
            mantra=_get_mantra(),
            level=level,
        )
    elif level is not None:
        _gate.level = level
        _gate.threshold = 1 if level == "strict" else 5
    return _gate


@mcp.tool()
def mantrai_read() -> str:
    """Return the current mantra with level and principles."""
    mantra = _get_mantra()
    lines = [f"Level: {mantra.level}", ""]
    for i, p in enumerate(mantra.principles, 1):
        lines.append(f"{i}. {p.text}")
    if mantra.author:
        lines.append(f"\nAuthor: {mantra.author}")
    return "\n".join(lines)


@mcp.tool()
def mantrai_confirm(session_id: str, action_context: Optional[str] = None) -> str:
    """Log an acknowledgment of the mantra for this session."""
    tracker = _get_tracker()
    confirmation = tracker.log_confirmation(
        session_id=session_id,
        agent_id=os.environ.get("CLYDE_AGENT_ID", "unknown"),
        action_context=action_context or "mantra_acknowledged",
    )
    return f"Confirmed at {confirmation.timestamp.isoformat()} for session {session_id}"


@mcp.tool()
def mantrai_check(session_id: str) -> str:
    """Check compliance: time since last confirm, window status, action count."""
    gate = _get_gate()
    last = _get_tracker().last_confirmation(session_id)
    in_window = _get_tracker().compliance_window(session_id, gate.window_minutes)
    stats = _get_tracker().session_stats(session_id)

    lines = [
        f"Session: {session_id}",
        f"Level: {gate.level}",
        f"Actions since last injection: {gate.action_counter}",
        f"Threshold: {gate.threshold}",
        f"Compliance window: {'IN' if in_window else 'OUT'} ({gate.window_minutes} min)",
        f"Total confirmations: {stats['count']}",
    ]
    if last:
        lines.append(f"Last confirmed: {last.timestamp.isoformat()}")
    else:
        lines.append("Last confirmed: NEVER")
    return "\n".join(lines)


@mcp.tool()
def mantrai_inject(session_id: str) -> str:
    """Force immediate mantra re-injection for this session."""
    gate = _get_gate()
    result = gate.before_action("forced_injection", session_id)
    if result.require_reinjection:
        return f"MANTRA INJECTION REQUIRED\n\n{result.mantra_block}"
    return f"No injection needed. Actions since last: {result.action_count}"


@mcp.tool()
def mantrai_compliance_log(session_id: str, limit: int = 10) -> str:
    """Return confirmation history for a session."""
    tracker = _get_tracker()
    logs = tracker.compliance_log(session_id, limit)
    if not logs:
        return f"No confirmations found for session {session_id}"
    lines = [f"Compliance log for {session_id} (last {len(logs)} entries):", ""]
    for entry in logs:
        ctx = entry.action_context or "ack"
        lines.append(f"- {entry.timestamp.isoformat()} | {ctx} | ack={entry.acknowledged}")
    return "\n".join(lines)


@mcp.tool()
def mantrai_set_level(session_id: str, level: str) -> str:
    """Change the mantra intensity level for this session: strict, normal, or off."""
    if level not in ("strict", "normal", "off"):
        return f"Invalid level: {level}. Choose strict, normal, or off."
    gate = _get_gate(level=level)
    gate.reset_counter()
    return f"Level set to '{level}' for session {session_id}. Threshold: {gate.threshold}."


@mcp.tool()
def mantrai_validate_custom(file_path: str) -> str:
    """Validate a custom mantra file against the schema."""
    path = Path(file_path)
    if not path.exists():
        return f"File not found: {file_path}"
    content = path.read_text(encoding="utf-8")
    valid, errors = validate_mantra(content)
    if valid and not errors:
        return "Valid mantra file."
    lines = []
    if not valid:
        lines.append("INVALID mantra file:")
    else:
        lines.append("Valid with warnings:")
    for e in errors:
        lines.append(f"- {e}")
    return "\n".join(lines)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
