from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import click
import questionary

from mantrai.session.gate import ActionGate
from mantrai.session.tracker import SessionTracker
from mantrai.core.config import get_db_path, load_config
from mantrai.core.mantra import get_default_mantra, load_mantra, validate_mantra
from mantrai.core.agent_setup import (
    get_detected_agents,
    install_claude_code_hook,
    install_cursor_mcp,
)


@click.group(invoke_without_command=True)
@click.option("--global", "edit_global", is_flag=True, help="Edit global mantra")
@click.option("--project", "edit_project", is_flag=True, help="Edit project-level mantra")
@click.option("--folder", "edit_folder", is_flag=True, help="Edit folder-level mantra")
@click.pass_context
def cli(ctx, edit_global, edit_project, edit_folder):
    """MantrAI — Self-reinforcing agent instruction primitive.

    With no subcommand, initializes a folder-level mantra in the current directory.
    Use --global, --project, or --folder to edit the respective mantra.
    """
    category: str | None = None
    target_path: Path | None = None
    if edit_global:
        category = "global"
        target_path = Path("~/.mantrai/mantra.md").expanduser()
    elif edit_project:
        category = "project"
        from mantrai.core.mantra import _find_project_root
        root = _find_project_root()
        if root is None:
            click.echo("ERROR: No project root found (no .git or pyproject.toml)")
            sys.exit(1)
        target_path = root / ".mantrai.md"
    elif edit_folder:
        category = "folder"
        target_path = Path.cwd() / ".mantrai.md"

    if category and target_path:
        _edit_category(category, target_path)
        return

    if ctx.invoked_subcommand is None:
        # No args: print current effective mantra
        mantra = load_mantra()
        click.echo(mantra.render())


@cli.command()
@click.option("--custom", "custom_path", type=click.Path(exists=True), help="Path to custom mantra file")
def read(custom_path):
    """Print the current mantra."""
    path = Path(custom_path) if custom_path else None
    mantra = load_mantra(path)
    click.echo(mantra.render())


@cli.command()
@click.option("--session-id", default=lambda: str(uuid.uuid4())[:8], help="Session identifier")
@click.option("--context", default="cli_ack", help="Action context for the log")
def confirm(session_id, context):
    """Log a mantra acknowledgment."""
    cfg = load_config()
    tracker = SessionTracker(db_path=get_db_path(cfg))
    confirmation = tracker.log_confirmation(
        session_id=session_id,
        agent_id=os.environ.get("CLYDE_AGENT_ID", "cli"),
        action_context=context,
    )
    click.echo(f"Confirmed at {confirmation.timestamp.isoformat()} for session {session_id}")


@cli.command()
@click.option("--session-id", default=lambda: str(uuid.uuid4())[:8], help="Session identifier")
def check(session_id):
    """Check compliance status for a session."""
    cfg = load_config()
    tracker = SessionTracker(db_path=get_db_path(cfg))
    mantra = load_mantra()
    gate = ActionGate(tracker, mantra)
    result = gate.before_action("cli_check", session_id)
    in_window = tracker.compliance_window(session_id, gate.window_minutes)
    stats = tracker.session_stats(session_id)

    click.echo(f"Session: {session_id}")
    click.echo(f"Level: {gate.level}")
    click.echo(f"Actions since last injection: {result.action_count}")
    click.echo(f"Threshold: {result.threshold}")
    click.echo(f"Compliance window: {'IN' if in_window else 'OUT'} ({gate.window_minutes} min)")
    click.echo(f"Total confirmations: {stats['count']}")
    if result.last_confirmed:
        click.echo(f"Last confirmed: {result.last_confirmed.timestamp.isoformat()}")
    else:
        click.echo("Last confirmed: NEVER")


@cli.command()
@click.option("--session-id", default=lambda: str(uuid.uuid4())[:8], help="Session identifier")
def inject(session_id):
    """Force immediate mantra injection."""
    cfg = load_config()
    tracker = SessionTracker(db_path=get_db_path(cfg))
    mantra = load_mantra()
    gate = ActionGate(tracker, mantra)
    result = gate.before_action("forced_injection", session_id)
    if result.require_reinjection:
        click.echo("MANTRA INJECTION REQUIRED")
        click.echo("")
        click.echo(result.mantra_block)
    else:
        click.echo(f"No injection needed. Actions since last: {result.action_count}")


@cli.command()
@click.option("--session-id", default=lambda: str(uuid.uuid4())[:8], help="Session identifier")
@click.option("--limit", default=20, help="Number of log entries to show")
def log(session_id, limit):
    """Show confirmation history for a session."""
    cfg = load_config()
    tracker = SessionTracker(db_path=get_db_path(cfg))
    entries = tracker.compliance_log(session_id, limit)
    if not entries:
        click.echo(f"No confirmations found for session {session_id}")
        return
    click.echo(f"Compliance log for {session_id} (last {len(entries)} entries):")
    click.echo("")
    for entry in entries:
        ctx = entry.action_context or "ack"
        click.echo(f"- {entry.timestamp.isoformat()} | {ctx} | ack={entry.acknowledged}")


@cli.command()
@click.option("--session-id", envvar="MANTRAI_SESSION_ID", default="hook", help="Session identifier")
@click.option("--limit", default=10, help="Number of audit entries to show")
def audit(session_id, limit):
    """Show contextual injection audit for a session."""
    cfg = load_config()
    tracker = SessionTracker(db_path=get_db_path(cfg))
    entries = tracker.audit_log(session_id, limit)
    if not entries:
        click.echo(f"No injection audit found for session {session_id}")
        return
    click.echo(f"Injection audit for {session_id} (last {len(entries)} entries):")
    click.echo("")
    for entry in entries:
        click.echo(f"- {entry['timestamp'].isoformat()} | {entry['selected_count']}/{entry['total_principles']} principles")
        click.echo(f"  Prompt: {entry['prompt_preview'][:80]}...")
        if entry["fallback"]:
            click.echo(f"  Mode: FALLBACK (no keywords matched)")
        else:
            keywords = entry.get("matched_keywords", {})
            for principle, hits in list(keywords.items())[:3]:
                click.echo(f"  Matched: {principle} → {', '.join(hits[:3])}")
        click.echo("")


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
def validate(file_path):
    """Validate a custom mantra file."""
    content = Path(file_path).read_text(encoding="utf-8")
    valid, errors = validate_mantra(content)
    if valid and not errors:
        click.echo("Valid mantra file.")
        sys.exit(0)
    for e in errors:
        click.echo(f"{'WARNING' if 'WARNING' in e else 'ERROR'}: {e}")
    sys.exit(0 if valid else 1)


@cli.command()
@click.option("--session-id", envvar="MANTRAI_SESSION_ID", default="hook", help="Session identifier")
def hook(session_id):
    """Prompt injection hook. Reads prompt from stdin, prepends mantra if required.

    Works with any agent that supports prompt hooks or stdin/stdout filters.
    Example Claude Code configuration in .claude/settings.json:

    { "user-prompt-submit-hook": "mantrai hook" }

    Or pipe manually: echo "prompt" | mantrai hook
    """
    prompt_text = sys.stdin.read()
    if not prompt_text.strip():
        click.echo(prompt_text, nl=False)
        return

    # Block self-modification attempts
    lower = prompt_text.lower()
    if any(k in lower for k in ("mantra", ".mantrai.md", "mantras/default")) and any(
        k in lower for k in (
            "edit", "change", "modify", "replace", "update", "rewrite", "delete",
            "overwrite", "remove", "clear", "truncate", "wipe", "reset", "alter",
            "redefine", "drop", "purge",
        )
    ):
        click.echo(
            "[BLOCKED] Agent cannot alter its own mantra. "
            "Use `mantrai init --paste` with manual paste to change the mantra.[/BLOCKED]\n\n"
            + prompt_text,
            nl=False,
        )
        return

    try:
        cfg = load_config()
        tracker = SessionTracker(db_path=get_db_path(cfg))
        mantra = load_mantra()
        gate = ActionGate(tracker, mantra)
        result = gate.before_action("prompt", session_id)

        if result.require_reinjection:
            from mantrai.core.detector import coordinate_injection, get_injection_strategy
            from mantrai.core.selector import get_selection_audit, render_contextual_block, select_principles

            # Contextual mode: select only principles relevant to the prompt
            if cfg.get("contextual_mode", True):
                selected = select_principles(prompt_text, mantra.principles)
                mantra_block = render_contextual_block(
                    selected,
                    level=mantra.level,
                )
                audit = get_selection_audit(prompt_text, mantra.principles, selected)
                tracker.log_injection_audit(session_id, audit)
            else:
                mantra_block = result.mantra_block

            # Determine strategy: piggyback on MemPalace or direct injection
            # Pass prompt_text to detect [MEM] markers in stdin
            strategy = get_injection_strategy(cfg, prompt_text)
            existing = prompt_text if strategy == "piggyback" else None

            # Coordinate injection
            combined = coordinate_injection(
                mantra_block=mantra_block,
                strategy=strategy,
                existing_injection=existing,
            )
            
            # Reset counter and log
            gate.reset_counter()
            tracker.log_confirmation(
                session_id=session_id,
                agent_id="hook",
                action_context="injected",
            )
            
            if strategy == "piggyback":
                # Prepend marker for MemPalace to position
                click.echo("[MANTRAI_L05]" + combined, nl=False)
            else:
                click.echo(combined + "\n" + prompt_text, nl=False)
        else:
            click.echo(prompt_text, nl=False)
    except Exception as exc:
        click.echo(f"[MANTRAI ERROR] {exc}", err=True)
        click.echo(prompt_text, nl=False)


@cli.command()
def serve():
    """Start the MantrAI MCP server (stdio)."""
    from mantrai.mcp_server.server import main
    main()


def _configure_agents(target: Path, yes: bool) -> None:
    """Detect and configure supported agents."""
    agents = get_detected_agents()

    if not agents:
        click.echo("No supported agents detected in PATH or current directory.")
        click.echo("")
        click.echo("To use MantrAI with any agent, pipe prompts through it:")
        click.echo("  echo 'your prompt' | mantrai hook")
        click.echo("Or run the MCP server: mantrai serve")
        return

    click.echo(f"Detected agents: {', '.join(agents)}")
    click.echo("")

    if "claude-code" in agents:
        if yes or click.confirm("Install Claude Code hook?", default=True):
            ok, msg = install_claude_code_hook(target)
            click.echo(msg)

    if "cursor" in agents:
        if yes or click.confirm("Install Cursor MCP config?", default=True):
            ok, msg = install_cursor_mcp(target)
            click.echo(msg)

    if "codex" in agents and "claude-code" not in agents:
        click.echo("Codex detected. Add `mantrai hook` to your Codex wrapper script.")

    click.echo("")
    click.echo("Setup complete. Run `mantrai read` to verify your mantra.")


@cli.command(name="setup")
@click.option("--dir", "target_dir", default=".", help="Target directory for agent configs")
@click.option("--yes", "-y", is_flag=True, help="Auto-confirm agent configuration")
def setup_cmd(target_dir, yes):
    """Auto-detect and configure MantrAI for supported agents."""
    _configure_agents(Path(target_dir), yes)


@cli.command()
@click.option("--dir", "target_dir", default=".", help="Target directory to install mantra into")
@click.option("--mantra", "mantra_path", help="Path to custom mantra file")
@click.option("--paste", is_flag=True, help="Paste mantra content from stdin")
@click.option("--interactive", "-i", is_flag=True, help="Guided interactive mantra creation")
@click.option("--setup", is_flag=True, help="Configure detected agents after installing mantra")
def init(target_dir, mantra_path, paste, interactive, setup):
    """Install mantra into a project directory.

    With --paste, reads mantra content from stdin until EOF (Ctrl+D).
    With --interactive, guides you through customizing the default mantra.
    With --setup, auto-configures detected agents after installation.
    """
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    dest = target / ".mantrai.md"

    if interactive:
        _interactive_init(dest)
        return

    if paste:
        click.echo("Paste your mantra below. Press Ctrl+D when done:")
        content = sys.stdin.read()
        valid, errors = validate_mantra(content)
        if not valid:
            for e in errors:
                click.echo(f"ERROR: {e}")
            sys.exit(1)
        dest.write_text(content, encoding="utf-8")
        click.echo(f"Installed pasted mantra to {dest}")
        return

    if mantra_path:
        content = Path(mantra_path).read_text(encoding="utf-8")
        valid, errors = validate_mantra(content)
        if not valid:
            for e in errors:
                click.echo(f"ERROR: {e}")
            sys.exit(1)
        dest.write_text(content, encoding="utf-8")
        click.echo(f"Installed custom mantra from {mantra_path} to {dest}")
        return

    # Default: install bundled default mantra
    try:
        from importlib.resources import files
    except ImportError:
        from importlib_resources import files  # type: ignore[no-redef]
    ref = files("mantrai").joinpath("mantras/default.md")
    content = ref.read_text(encoding="utf-8")
    dest.write_text(content, encoding="utf-8")
    click.echo(f"Installed default mantra to {dest}")

    if setup:
        click.echo("")
        _configure_agents(target, yes=False)


def _edit_category(category: str, target_path: Path) -> None:
    """Launch checkbox TUI to edit principles for a category in the target file."""
    from mantrai.core.schema import Mantra, Principle

    defaults = get_default_mantra()
    default_principles = [p for p in defaults.principles if p.category == category]

    # Load existing file to preserve metadata and non-default principles
    existing_mantra = None
    existing_for_cat: list = []
    if target_path.exists():
        try:
            existing_mantra = load_mantra(target_path)
            existing_for_cat = [p for p in existing_mantra.principles if p.category == category]
        except Exception:
            pass

    # Build choices: defaults always checked, plus existing non-defaults checked
    seen: set[str] = set()
    choices: list = []
    for p in default_principles:
        seen.add(p.text)
        choices.append(questionary.Choice(title=p.text, checked=True))
    for p in existing_for_cat:
        if p.text not in seen:
            seen.add(p.text)
            choices.append(questionary.Choice(title=p.text, checked=True))
    choices.append(questionary.Choice(title="[Add custom principle...]", checked=False))

    click.echo(f"=== {category.capitalize()} Mantra — Space to toggle, Enter to save ===")
    selected = questionary.checkbox(
        "Select principles to keep:",
        choices=choices,
    ).ask()

    if selected is None:
        click.echo("Cancelled.")
        return

    custom_principles: list[str] = []
    if "[Add custom principle...]" in selected:
        while True:
            text = questionary.text("Enter custom principle (empty to finish):").ask()
            if not text or not text.strip():
                break
            custom_principles.append(text.strip())
        selected = [s for s in selected if s != "[Add custom principle...]"]

    # Rebuild mantra preserving other categories exactly as they are
    all_principles: list = []
    if existing_mantra is not None:
        for p in existing_mantra.principles:
            if p.category != category:
                all_principles.append(p)

    for text in selected:
        all_principles.append(Principle(text=text, category=category))
    for text in custom_principles:
        all_principles.append(Principle(text=text, category=category))

    if not all_principles:
        click.echo("ERROR: At least one principle required.")
        sys.exit(1)

    new_mantra = Mantra(
        level=existing_mantra.level if existing_mantra else defaults.level,
        author=existing_mantra.author if existing_mantra else defaults.author,
        token=existing_mantra.token if existing_mantra else defaults.token,
        principles=all_principles,
    )

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(new_mantra.to_markdown(), encoding="utf-8")
    total = len(selected) + len(custom_principles)
    click.echo(f"Saved {total} {category} principle(s) to {target_path}")


def _interactive_init(dest: Path) -> None:
    """Guide the user through creating a custom folder mantra."""
    from mantrai.core.schema import Mantra, Principle

    click.echo("")
    click.echo("=== MantrAI Interactive Setup ===")
    click.echo("")

    # Load base mantra
    base = load_mantra()
    click.echo("Current global mantra principles:")
    for i, p in enumerate(base.principles, 1):
        click.echo(f"  {i}. {p.text}")
    click.echo("")

    # Ask level
    level = click.prompt(
        "Level",
        type=click.Choice(["strict", "normal", "off"], case_sensitive=False),
        default=base.level,
    ).lower()

    # Start with base principles
    principles = [p.text for p in base.principles]

    while True:
        click.echo("")
        click.echo("Current principles:")
        for i, p in enumerate(principles, 1):
            click.echo(f"  {i}. {p}")
        click.echo("")
        click.echo("Options: (a)dd, (r)emove, (e)dit, (d)one")
        choice = click.prompt("What next", default="d").lower().strip()

        if choice in ("a", "add"):
            text = click.prompt("New principle text").strip()
            if text:
                principles.append(text)
        elif choice in ("r", "remove"):
            idx = click.prompt("Number to remove", type=int)
            if 1 <= idx <= len(principles):
                del principles[idx - 1]
            else:
                click.echo("Invalid number.")
        elif choice in ("e", "edit"):
            idx = click.prompt("Number to edit", type=int)
            if 1 <= idx <= len(principles):
                new_text = click.prompt("New text", default=principles[idx - 1])
                principles[idx - 1] = new_text.strip()
            else:
                click.echo("Invalid number.")
        elif choice in ("d", "done"):
            break
        else:
            click.echo("Unknown option.")

    if not principles:
        click.echo("ERROR: At least one principle required.")
        sys.exit(1)

    mantra = Mantra(
        level=level,
        principles=[Principle(text=p) for p in principles],
    )
    content = mantra.to_markdown()

    valid, errors = validate_mantra(content)
    if not valid:
        for e in errors:
            click.echo(f"ERROR: {e}")
        sys.exit(1)

    dest.write_text(content, encoding="utf-8")
    click.echo("")
    click.echo(f"Installed interactive mantra to {dest}")


@cli.command()
@click.option("--host", default="127.0.0.1", help="Host to bind")
@click.option("--port", default=8765, help="Port to bind")
def gui(host, port):
    """Start the MantrAI web GUI."""
    from mantrai.web.server import start_server
    start_server(host=host, port=port)


if __name__ == "__main__":
    cli()
