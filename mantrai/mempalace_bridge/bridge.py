from __future__ import annotations

import json
import subprocess
from typing import Optional

from mantrai.core.mantra import get_default_mantra
from mantrai.core.schema import Mantra

MEMPALACE_SEARCH_QUERY = "mantra principles standing orders"
MEMPALACE_WING = ".mempalace"
MEMPALACE_ROOM = "mantras"


def search_mempalace_cli() -> Optional[str]:
    """Fallback: shell out to mempalace CLI."""
    try:
        result = subprocess.run(
            [
                "python3",
                "-m",
                "mempalace.cli",
                "search",
                MEMPALACE_SEARCH_QUERY,
                "--wing",
                MEMPALACE_WING,
                "--room",
                MEMPALACE_ROOM,
                "--limit",
                "1",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def search_mempalace_mcp() -> Optional[str]:
    """Primary: call mempalace via MCP client if available.

    This requires the mempalace MCP server to be registered and accessible.
    In a real MCP client context this would use the MCP client SDK.
    For now, this is a stub that falls back to CLI mode.
    """
    # TODO: implement true MCP client mode using mcp.client
    # For now, delegate to CLI fallback
    return None


def get_mantra_from_mempalace() -> Optional[Mantra]:
    """Retrieve mantra from MemPalace. Returns None if unavailable."""
    raw = search_mempalace_mcp() or search_mempalace_cli()
    if raw is None:
        return None
    # Attempt to parse raw text as mantra content
    try:
        from mantrai.core.mantra import parse_mantra
        return parse_mantra(raw)
    except Exception:
        return None


def get_combined_mantra() -> Mantra:
    """Get mantra from MemPalace if available, otherwise return default."""
    mp_mantra = get_mantra_from_mempalace()
    if mp_mantra is not None:
        return mp_mantra
    return get_default_mantra()
