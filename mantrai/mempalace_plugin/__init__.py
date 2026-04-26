"""
MemPalace Plugin — Universal MantrAI Injection

Registers MantrAI as an L0.5 layer in MemPalace's wake-up stack.
Provides direction enforcement universally across all MemPalace-aware clients.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    from mempalace.layers import WakeUpLayer
except ImportError:
    WakeUpLayer = None


def register_mantrai_layer() -> None:
    """
    Register MantrAI as L0.5 layer with MemPalace.
    
    This makes MantrAI directions available in every MemPalace-injected session,
    regardless of client (Claude Code, Codex, Axiom, Hermes, etc.).
    """
    
    if WakeUpLayer is None:
        return
    
    class MantraLayer(WakeUpLayer):
        """L0.5 — Imperative directions between identity and story."""
        
        @property
        def level(self) -> int:
            return 5  # Between L0 (0) and L1 (10)
        
        @property
        def name(self) -> str:
            return "mantra"
        
        def render(self, context: dict[str, Any] | None = None) -> str:
            """Return formatted mantra block."""
            from mantrai.core.mantra import load_mantra
            
            try:
                mantra = load_mantra()
                return f"## L0.5 — Mantra\n\n{mantra.render()}"
            except Exception:
                return "## L0.5 — Mantra\n\n> **ABSOLUTELY NO SIMULATIONS**\n"
    
    # Register with MemPalace layer system
    try:
        from mempalace.layers import register_layer
        register_layer(MantraLayer())
    except Exception:
        # MemPalace may not support plugin layers yet
        # Fall back to environment marker for detection
        os.environ["MANTRAI_MEMPALACE_PLUGIN"] = "registered"


# Auto-register on import if MemPalace present
if __import__("importlib").util.find_spec("mempalace") is not None:
    register_mantrai_layer()
