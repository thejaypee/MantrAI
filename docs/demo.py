#!/usr/bin/env python3
"""
MantrAI Interactive Demo
========================

A self-contained, runnable script that demonstrates MantrAI's core
capabilities using **real** function calls and actual data — no mocks,
o fakes, and no stubs.

Run it from the repository root:
    python docs/demo.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Ensure the repo root is on PYTHONPATH so absolute imports work even if the
# package hasn't been installed into the active environment.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mantrai.core.schema import Mantra, Principle
from mantrai.core.mantra import get_default_mantra, validate_mantra
from mantrai.core.selector import (
    get_selection_audit,
    render_contextual_block,
    select_principles,
)
from mantrai.session.gate import ActionGate
from mantrai.session.injector import MantraInjector
from mantrai.session.tracker import SessionTracker

# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------
G = "\033[92m"    # green  (pass / success)
R = "\033[91m"    # red    (fail / error)
Y = "\033[93m"    # yellow (warning / skip)
C = "\033[96m"    # cyan   (info / highlight)
B = "\033[1m"     # bold
RST = "\033[0m"   # reset


def print_banner() -> None:
    print(f"{C}{B}")
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║                    MantrAI  –  Interactive Demo                        ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    print(f"{RST}")
    print(
        "MantrAI injects behavioural mantras into AI agents to enforce "
        "discipline, transparency, and accountability.\n"
    )


def section(title: str) -> None:
    print(f"\n{Y}{B}▶ {title}{RST}\n")


def info(label: str, value: object) -> None:
    print(f"  {B}{label}:{RST} {value}")


def ok(msg: str) -> None:
    print(f"  {G}✓ {msg}{RST}")


def bad(msg: str) -> None:
    print(f"  {R}✗ {msg}{RST}")


def warn(msg: str) -> None:
    print(f"  {Y}⚠ {msg}{RST}")


# ---------------------------------------------------------------------------
# Main demo flow
# ---------------------------------------------------------------------------

def main() -> None:
    print_banner()

    # =====================================================================
    # 1. Load the default mantra
    # =====================================================================
    section("1. Loading the Default Mantra")
    default_mantra = get_default_mantra()
    info("Level", default_mantra.level)
    info("Author", default_mantra.author or "N/A")
    info("Token", (default_mantra.token or "N/A")[:50] + "…")
    info("Total principles", len(default_mantra.principles))
    print(f"\n{C}--- First 6 lines of rendered default mantra ---{RST}")
    for line in default_mantra.render().splitlines()[:6]:
        print(f"  {line}")
    print(f"  … ({len(default_mantra.render().splitlines())} lines total)")

    # =====================================================================
    # 2. Create a custom mantra programmatically and validate it
    # =====================================================================
    section("2. Custom Mantra Creation & Validation")
    custom = Mantra(
        level="normal",
        author="demo-user",
        token="DEMO-TOKEN-123",
        principles=[
            Principle(
                text="Always write tests before committing code.",
                category="project",
            ),
            Principle(
                text="Document every public API function.",
                category="project",
            ),
            Principle(
                text="Never commit secrets to version control.",
                category="global",
            ),
        ],
    )
    custom_md = custom.to_markdown()
    valid, errors = validate_mantra(custom_md)
    if valid:
        ok("Custom mantra passed validation")
    else:
        bad("Custom mantra failed validation")
        for err in errors:
            print(f"    {R}- {err}{RST}")

    # Intentionally show a *failed* validation as well so the demo
    # illustrates both outcomes.
    bad_md = "# Bad Mantra\n\nMissing header and principles.\n"
    valid2, errors2 = validate_mantra(bad_md)
    if not valid2:
        bad("Invalid mantra correctly rejected")
        for err in errors2:
            print(f"    {R}- {err}{RST}")
    else:
        ok("Unexpected pass for bad mantra")

    # =====================================================================
    # 3. SessionTracker (SQLite-backed confirmation log)
    # =====================================================================
    section("3. SessionTracker — Confirmation Log & Stats")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "demo_sessions.db"
        tracker = SessionTracker(db_path=db_path)
        session_id = "demo-session"

        # Log a handful of confirmations
        tracker.log_confirmation(
            session_id, agent_id="agent-alpha", action_context="read file"
        )
        tracker.log_confirmation(
            session_id, agent_id="agent-alpha", action_context="edit file"
        )
        tracker.log_confirmation(
            session_id, agent_id="agent-alpha", action_context="run tests"
        )
        ok("3 confirmations logged to SQLite")

        # Compliance window check
        in_window = tracker.compliance_window(session_id, window_minutes=5)
        info("Within 5-min compliance window", "Yes" if in_window else "No")

        # Stats
        stats = tracker.session_stats(session_id)
        info("Total confirmations", stats["count"])
        info(
            "First confirmation",
            stats["first"].isoformat() if stats["first"] else "N/A",
        )
        info(
            "Last confirmation",
            stats["last"].isoformat() if stats["last"] else "N/A",
        )

        # Audit log (empty so far — contextual selection will populate it)
        audit = tracker.audit_log(session_id)
        info("Audit records", len(audit))

    # =====================================================================
    # 4. ActionGate — strict / normal / off levels
    # =====================================================================
    section("4. ActionGate — Reinjection Logic")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "gate_demo.db"
        tracker = SessionTracker(db_path=db_path)
        gate_session = "gate-session"
        mantra = get_default_mantra()

        # --- STRICT ------------------------------------------------------
        print(f"\n  {B}Strict level (threshold = 1, every action injects):{RST}")
        strict_gate = ActionGate(tracker=tracker, mantra=mantra, level="strict")
        for i in range(1, 4):
            result = strict_gate.before_action(f"action_{i}", gate_session)
            status = f"{G}INJECTED{RST}" if result.require_reinjection else f"{R}SKIPPED{RST}"
            print(
                f"    action {i}: {status}  "
                f"(count={result.action_count}, threshold={result.threshold})"
            )

        # --- NORMAL ------------------------------------------------------
        # Pre-seed a confirmation so the compliance window is active.
        tracker.log_confirmation(
            gate_session, agent_id="agent-beta", action_context="init"
        )
        print(
            f"\n  {B}Normal level (threshold = 5, inject every N actions or "
            f"outside window):{RST}"
        )
        normal_gate = ActionGate(tracker=tracker, mantra=mantra, level="normal")
        for i in range(1, 7):
            result = normal_gate.before_action(f"action_{i}", gate_session)
            status = (
                f"{G}INJECTED{RST}"
                if result.require_reinjection
                else f"{Y}SKIPPED{RST}"
            )
            print(
                f"    action {i}: {status}  "
                f"(count={result.action_count}, threshold={result.threshold})"
            )

        # --- OFF ---------------------------------------------------------
        print(f"\n  {B}Off level (no injection):{RST}")
        off_gate = ActionGate(tracker=tracker, mantra=mantra, level="off")
        for i in range(1, 4):
            result = off_gate.before_action(f"action_{i}", gate_session)
            status = (
                f"{G}INJECTED{RST}"
                if result.require_reinjection
                else f"{Y}SKIPPED{RST}"
            )
            print(
                f"    action {i}: {status}  "
                f"(count={result.action_count}, threshold={result.threshold})"
            )

    # =====================================================================
    # 5. Contextual principle selection
    # =====================================================================
    section("5. Contextual Principle Selection")
    prompt = "How do I handle security vulnerabilities?"
    selected = select_principles(prompt, default_mantra.principles)
    audit_data = get_selection_audit(prompt, default_mantra.principles, selected)
    info("Prompt", prompt)
    info("Total principles", audit_data["total_principles"])
    info("Selected principles", audit_data["selected_count"])
    info("Fallback (all returned)", audit_data["fallback"])
    print(f"\n  {B}Keyword matches:{RST}")
    for principle_text, hits in audit_data["matched_keywords"].items():
        print(f"    {C}{principle_text[:60]}…{RST}")
        print(f"      hits: {', '.join(hits)}")

    # =====================================================================
    # 6. Rendered output — what the agent actually sees
    # =====================================================================
    section("6. Rendered Injection Output")
    print(f"{C}--- Contextual block (selected principles only) ---{RST}")
    contextual = render_contextual_block(selected, level=default_mantra.level)
    print(contextual)

    print(f"{C}--- Full block (MantraInjector with strict level) ---{RST}")
    injector = MantraInjector(default_mantra)
    print(injector.inject())

    # =====================================================================
    # 7. Summary
    # =====================================================================
    section("7. Summary")
    print(f"  {G}•{RST} Default mantra loaded ({len(default_mantra.principles)} principles)")
    print(f"  {G}•{RST} Custom mantra created and validated")
    print(f"  {G}•{RST} SessionTracker persisted confirmations to SQLite")
    print(f"  {G}•{RST} ActionGate showed strict/normal/off reinjection behaviour")
    print(
        f"  {G}•{RST} Contextual selection matched {audit_data['selected_count']} "
        f"principle(s) for the security prompt"
    )
    print(f"  {G}•{RST} Rendered blocks display exactly what an agent receives")
    print(f"\n{B}Demo complete. MantrAI is ready to enforce discipline.{RST}\n")


if __name__ == "__main__":
    main()
