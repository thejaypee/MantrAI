from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import click

from mantrai.antifunnel.gate import ActionGate
from mantrai.antifunnel.session import SessionTracker
from mantrai.core.config import get_db_path, load_config
from mantrai.core.mantra import load_mantra, validate_mantra


@click.group()
def cli():
    """MantrAI — Self-reinforcing agent instruction primitive."""
    pass


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
def serve():
    """Start the MantrAI MCP server (stdio)."""
    from mantrai.mcp_server.server import main
    main()


@cli.command()
@click.option("--dir", "target_dir", default=".", help="Target directory to install mantra into")
@click.option("--mantra", "mantra_path", help="Path to custom mantra file")
@click.option("--paste", is_flag=True, help="Paste mantra content from stdin")
def init(target_dir, mantra_path, paste):
    """Install mantra into a project directory.

    With --paste, reads mantra content from stdin until EOF (Ctrl+D).
    """
    if paste:
        click.echo("Paste your mantra below. Press Ctrl+D when done:")
        content = sys.stdin.read()
        valid, errors = validate_mantra(content)
        if not valid:
            for e in errors:
                click.echo(f"ERROR: {e}")
            sys.exit(1)
        tmp = Path(target_dir) / ".mantrai_pasted.md"
        tmp.write_text(content, encoding="utf-8")
        script = Path(__file__).parent.parent.parent / "scripts" / "mantrai-init.sh"
        if not script.exists():
            click.echo(f"Init script not found: {script}")
            sys.exit(1)
        subprocess.run(["bash", str(script), "--dir", target_dir, "--mantra", str(tmp)], check=False)
        tmp.unlink(missing_ok=True)
        return

    script = Path(__file__).parent.parent.parent / "scripts" / "mantrai-init.sh"
    if not script.exists():
        click.echo(f"Init script not found: {script}")
        sys.exit(1)
    cmd = ["bash", str(script), "--dir", target_dir]
    if mantra_path:
        cmd.extend(["--mantra", mantra_path])
    subprocess.run(cmd, check=False)


if __name__ == "__main__":
    cli()
