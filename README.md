# MantrAI

Self-reinforcing agent instruction primitive. Repeated mantra injection for continuous compliance.

## What Is This?

MantrAI ensures agents continuously re-read and acknowledge standing principles throughout a session — not just once at startup. It provides:

- **Categorized Mantras** — Global, Project, and Folder-level principles
- **MCP Server** — 7 tools Claude can call to check, confirm, and inject mantras
- **Checkbox Editor** — Interactive TUI (`--global`, `--project`, `--folder`) for quick setup
- **Web GUI** — Browser-based editor with three tabs
- **Session Logger** — SQLite-backed audit trail of every acknowledgment
- **MemPalace Bridge** — Pulls mantras from MemPalace when available
- **Standalone CLI** — Works without Claude (`mantrai read`, `mantrai confirm`, etc.)
- **Prompt Hook** — Injects mantra before every prompt via `user-prompt-submit-hook`

## Install

```bash
# From the project directory
uv pip install -e .

# Or with pip
pip install -e .
```

The `mantrai` binary is installed into your virtual environment:

```bash
/home/sauly/mantrai/.venv/bin/mantrai --help

# Or activate the venv first
source /home/sauly/mantrai/.venv/bin/activate
mantrai --help
```

## Quick Start

```bash
mantrai read              # Print current mantra with categories
mantrai serve             # Start MCP server
mantrai gui               # Start web GUI on localhost:8765
mantrai --global          # Edit global principles (checkbox TUI)
mantrai --project         # Edit project-level principles
mantrai --folder          # Edit folder-level principles
mantrai                   # Initialize folder-level mantra in current directory
```

## Three-Level Mantra Hierarchy

MantrAI resolves mantras in this order:

1. **Folder level** — `.mantrai.md` in current directory
2. **Project level** — `.mantrai.md` in project root (nearest `.git` or `pyproject.toml`)
3. **Global level** — `~/.mantrai/mantra.md`
4. **Bundled default** — Package default (categorized)

This means you can set global rules, override them per project, and override again per folder.

## Categories

Each mantra is divided into three categories:

- **Global** — Universal agent behavior: no simulations, no lying, read before write, security, etc.
- **Project** — Workflow rules: plan first, /init, checklist, build mode, demo, wait for confirmation
- **Folder** — Cross-repo integration: treat repos as modules, follow upstream docs, adapters, mempalace

## MCP Tools

| Tool | Purpose |
| --- | --- |
| `mantrai_read` | Return current mantra with level and principles |
| `mantrai_confirm` | Log acknowledgment for a session |
| `mantrai_check` | Check compliance status |
| `mantrai_inject` | Force immediate mantra re-injection |
| `mantrai_compliance_log` | Show confirmation history |
| `mantrai_set_level` | Change intensity: strict, normal, off |
| `mantrai_validate_custom` | Validate a custom mantra file |

## CLI Commands

```bash
mantrai read                          # Print current mantra
mantrai confirm --session-id ID       # Log acknowledgment
mantrai check --session-id ID         # Check compliance
mantrai inject --session-id ID        # Force injection
mantrai log --session-id ID           # Show history
mantrai validate <file.md>            # Validate custom mantra
mantrai serve                         # Start MCP server (stdio)
mantrai init --dir /path/to/project   # Install mantra into project
mantrai init --paste --dir .          # Paste mantra from stdin
mantrai init --interactive --dir .    # Guided mantra creation
mantrai gui                           # Start web GUI
mantrai --global                      # Edit global mantra (TUI)
mantrai --project                     # Edit project mantra (TUI)
mantrai --folder                      # Edit folder mantra (TUI)
mantrai                               # Initialize folder mantra in cwd
```

## Levels

- `strict` — Re-inject every action, require confirmation every time
- `normal` — Re-inject every 5 actions or when compliance window expires
- `off` — Log only, no injection

## Custom Mantras

Create a file with your principles:

```markdown
## Agent Mantra — Follow This At All Times

### Global
> **ABSOLUTELY NO SIMULATIONS**

### Project
> **Plan first**

### Folder
> **Treat repositories as modules**

---
```

Then install it:

```bash
mantrai validate my-mantra.md
mantrai init --mantra my-mantra.md --dir /path/to/project
```

Or paste directly:

```bash
mantrai init --paste --dir .
```

Or use the interactive checkbox editor:

```bash
mantrai --global
```

Or the web GUI:

```bash
mantrai gui
```

## MemPalace Integration

When MemPalace MCP is available, `mantrai_read` can pull mantras from the palace first, then fall back to the local default. The bridge supports both MCP client mode and CLI fallback mode.

## Tests

```bash
pytest tests/ -v
bash tests/test-mantrai.sh
```
