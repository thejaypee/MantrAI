# MantrAI

Self-reinforcing agent instruction primitive. Repeated mantra injection for continuous compliance.

## Install

```bash
pip install mantrai
# or
uv tool install mantrai
```

## What Is This?

MantrAI ensures agents continuously re-read and acknowledge standing principles throughout a session — not just once at startup. It provides:

- **MCP Server** — 7 tools Claude can call to check, confirm, and inject mantras
- **Session Logger** — SQLite-backed audit trail of every acknowledgment
- **MemPalace Bridge** — Pulls mantras from MemPalace when available
- **Standalone CLI** — Works without Claude (`mantrai read`, `mantrai confirm`, etc.)

## Quick Start

```bash
mantrai read              # Print default mantra
mantrai serve             # Start MCP server
```

## MCP Tools

| Tool | Purpose |
|---|---|
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
mantrai init --paste --dir .           # Paste mantra from stdin
```

## Levels

- `strict` — Re-inject every action, require confirmation every time
- `normal` — Re-inject every 5 actions or when compliance window expires
- `off` — Log only, no injection

## Custom Mantras

Create a file with your principles:

```markdown
## Agent Mantra — Follow This At All Times

> **ALWAYS WRITE TESTS FIRST.**
> **NEVER SKIP CODE REVIEW.**

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

## MemPalace Integration

When MemPalace MCP is available, `mantrai_read` can pull mantras from the palace first, then fall back to the local default. The bridge supports both MCP client mode and CLI fallback mode.

## Tests

```bash
pytest tests/ -v
bash tests/test-mantrai.sh
```
