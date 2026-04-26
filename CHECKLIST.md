# MantrAI — Implementation Checklist

## Done

- [x] FastMCP server with 7 tools (read, confirm, check, inject, compliance_log, set_level, validate_custom)
- [x] SQLite session tracker with compliance logging
- [x] Action gate: strict (every action), normal (every 5 actions), off (log only)
- [x] MemPalace bridge: MCP client mode + CLI fallback mode
- [x] Standalone CLI: read, confirm, check, inject, log, validate, serve, init
- [x] CLI `init --paste` support (reads mantra from stdin)
- [x] Folder-specific mantras via `.mantrai.md` in current directory
- [x] Package loads default mantra from package resources (works when installed globally)
- [x] 42 pytest tests — all passing
- [x] 10 bash integration tests — all passing
- [x] Global pip install verified (`pip install ~/mantrai` works)
- [x] `mantrai read` works from installed package
- [x] v2 branding removed from code, docs, CLI, and filenames
- [x] No Krewe/Tailscale/Ray references in the product
- [x] `user-prompt-submit-hook` for injecting mantra before every prompt
- [x] Three-level mantra hierarchy: global (~/.mantrai/mantra.md) → project (.mantrai.md in root) → folder (.mantrai.md in cwd)
- [x] Self-modification blocking: agent cannot edit its own mantra
- [x] `antifunnel` renamed to `session`
- [x] `mantrai` (no args) initializes folder-level mantra
- [x] Interactive init mode (`--interactive`)
- [x] Updated mempalace.yaml room structure

## Remaining

- [ ] Register with Anthropic MCP ecosystem / marketplace
- [ ] Submit to Bankr skill registry
- [ ] Publish to PyPI (`pip install mantrai` without local path)
- [ ] x402 paid tier (custom mantra generation)
- [ ] Web-based mantra builder
- [ ] More example mantras (security, design, data-science)
- [ ] GitHub Actions CI for test suite on PR
- [ ] Homebrew / install.sh one-liner
- [ ] `--list` flag to show available custom mantras

## File Structure

```
~/mantrai/
├── mantrai/
│   ├── core/
│   │   ├── mantra.py        # Loader, validator, parser (3-level hierarchy)
│   │   ├── schema.py        # Pydantic models
│   │   └── config.py        # Config loader
│   ├── session/
│   │   ├── tracker.py       # SQLite session tracker
│   │   ├── gate.py          # Action gate (strict/normal/off)
│   │   └── injector.py      # Mantra injector
│   ├── mcp_server/
│   │   └── server.py        # FastMCP server (7 tools)
│   ├── mempalace_bridge/
│   │   └── bridge.py        # MemPalace integration
│   ├── cli/
│   │   └── main.py          # Click CLI (8 commands + hook)
│   └── mantras/
│       └── default.md       # Bundled default mantra
├── tests/
│   ├── test_core.py         # 8 tests
│   ├── test_session.py      # 10 tests
│   ├── test_mcp_server.py   # 7 tests
│   ├── test_mempalace_bridge.py  # 4 tests
│   ├── test_cli.py          # 6 tests
│   └── test-mantrai.sh  # 10 bash tests
├── .claude/
│   └── settings.json        # user-prompt-submit-hook config
├── pyproject.toml
└── README.md
```

## Install

```bash
pip install ~/mantrai
# or after PyPI publish:
pip install mantrai
```

## Usage

```bash
mantrai read                          # Print mantra
mantrai serve                         # Start MCP server
mantrai init --paste --dir .          # Paste mantra from stdin
mantrai                               # Initialize folder-level mantra in cwd
```

Create `.mantrai.md` in any folder for folder-specific mantras.
Create `~/.mantrai/mantra.md` for global mantras.

## Mantra Levels

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
