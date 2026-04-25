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
- [x] 41 pytest tests — all passing
- [x] 10 bash integration tests — all passing
- [x] Global pip install verified (`pip install ~/mantrai-v2` works)
- [x] `mantrai read` works from installed package
- [x] v2 branding removed from code, docs, and CLI
- [x] No Krewe/Tailscale/Ray references in the product

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
- [ ] `--interactive` mode for guided mantra creation

## File Structure

```
~/mantrai-v2/
├── mantrai/
│   ├── core/
│   │   ├── mantra.py        # Loader, validator, parser
│   │   ├── schema.py        # Pydantic models
│   │   └── config.py        # Config loader
│   ├── antifunnel/
│   │   ├── session.py       # SQLite tracker
│   │   ├── gate.py          # Action gate
│   │   └── injector.py      # Mantra injector
│   ├── mcp_server/
│   │   └── server.py        # FastMCP server (7 tools)
│   ├── mempalace_bridge/
│   │   └── bridge.py        # MemPalace integration
│   ├── cli/
│   │   └── main.py          # Click CLI (8 commands)
│   └── mantras/
│       └── default.md       # Bundled default mantra
├── tests/
│   ├── test_core.py         # 8 tests
│   ├── test_antifunnel.py   # 10 tests
│   ├── test_mcp_server.py   # 7 tests
│   ├── test_mempalace_bridge.py  # 4 tests
│   ├── test_cli.py          # 6 tests
│   └── test-mantrai-v2.sh  # 10 bash tests
├── pyproject.toml
└── README.md
```

## Install

```bash
pip install ~/mantrai-v2
# or after PyPI publish:
pip install mantrai
```

## Usage

```bash
mantrai read                          # Print mantra
mantrai serve                         # Start MCP server
mantrai init --paste --dir .          # Paste mantra from stdin
```

Create `.mantrai.md` in any folder for folder-specific mantras.
