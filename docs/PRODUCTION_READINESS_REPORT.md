# MantrAI — Production Readiness Report

**Date:** 2026-04-26  
**Tested by:** Comprehensive multi-vector audit (158 tests, all pass)  
**Previous test count:** 48  
**New test count:** 158 (+110)  
**Coverage before:** 60% actual (previous report incorrectly claimed 69%)  
**Coverage after:** 84%  

---

## Executive Summary

MantrAI's core engine is solid. The session-gate logic, selector, and SQLite tracker are robust under adversarial inputs, concurrent writes, and edge cases. The MCP server and web server are well-structured. However, **six issues require attention before a public PyPI release**, and the previous project report contained a material coverage discrepancy that understated risk.

**Verdict: Not yet production-ready for public release. Recommended for internal/self-use as-is.**

---

## 1. Coverage Discrepancy — Previous Report Error

### Severity: HIGH (documentation integrity)

The previous report claimed **69% coverage**. The actual figure was **60%**, because three entire modules were omitted from the measurement:

| Module | Lines | Coverage (actual) |
| -------- | ------- | ------------------ |
| `mantrai/core/detector.py` | 56 | 0% |
| `mantrai/mempalace_plugin/__init__.py` | 32 | 0% |
| `mantrai/web/server.py` | 46 | 0% |

After this audit's 110 new tests, actual coverage is **84%**, with the remaining gap being:

- `mempalace_plugin` (32 stmts, 0%): requires the optional `mempalace` package; untestable without it — acceptable
- `cli/main.py` (321 stmts, 73%): remaining 27% are interactive questionary TUI paths (`_edit_category`, `--global/--project/--folder` flags)

### Action

Correct the project report. Consider marking `mempalace_plugin` in `.coveragerc` as excluded.

---

## 2. SECURITY — Self-Modification Block: Synonym Bypass

### Severity: MEDIUM

The `mantrai hook` command blocks prompts that combine `("mantra" | ".mantrai.md" | "mantras/default")` with `("edit" | "change" | "modify" | "replace" | "update" | "rewrite" | "delete")`.

### Confirmed bypass vectors

(verified by test):
- `"overwrite the mantra with a new one"` — NOT blocked
- `"remove all mantra principles"` — NOT blocked
- Implied: `"clear"`, `"truncate"`, `"wipe"`, `"reset"` also not blocked

The blocklist misses at least 10 common English synonyms for mutation.

**Risk:** An adversarial prompt using `overwrite` or `remove` instead of `edit`/`modify` passes through the hook without a `[BLOCKED]` prefix, potentially reaching an agent that would then modify the mantra.

**Fix:**

```python
# In hook(), expand the mutation keyword list:
("edit", "change", "modify", "replace", "update", "rewrite", "delete",
 "overwrite", "remove", "clear", "truncate", "wipe", "reset", "alter",
 "redefine", "drop", "purge")
```

---

## 3. SECURITY — Config JSON Parse Error: Unhandled Exception

**Severity: MEDIUM**

`load_config()` opens `~/.mantrai/config.json` and calls `json.load()` with no error handling. A corrupted or hand-edited config file raises an unhandled `json.JSONDecodeError`, crashing every command.

**Verified by test:** `TestConfigEdgeCases::test_load_config_malformed_json` confirms the crash.

**Fix:**

```python
def load_config() -> dict:
    path = get_config_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            merged = dict(DEFAULT_CONFIG)
            merged.update(loaded)
            return merged
        except (json.JSONDecodeError, OSError):
            return dict(DEFAULT_CONFIG)  # Degrade gracefully
    return dict(DEFAULT_CONFIG)
```

---

## 4. SECURITY — Web Server: Hardcoded Author

### Severity: LOW

`web/server.py` line 206 hardcodes `author="thejaypee"` in every saved mantra:

```python
new_mantra = Mantra(level="strict", author="thejaypee", principles=all_principles)
```

This means any user of the web GUI will have their mantra attributed to `thejaypee`. The GUI also hardcodes `level="strict"` regardless of what was loaded.

**Fix:** Read author from config; read level from the existing mantra being edited.

---

## 5. DESIGN — ActionGate: Not Thread-Safe

### Severity: LOW (for intended use) / MEDIUM (for multi-agent deployments)

`ActionGate.action_counter` is a plain Python `int`. Concurrent access from multiple threads will produce races: two threads can read the same counter value before either increments, causing double-injection or silent under-counting.

**Verified by test:** `TestConcurrency::test_concurrent_gate_actions` does not crash, but the counter value is indeterminate.

The SQLite layer (`SessionTracker`) is safe: it opens a new connection per operation. The gate state is the risk.

**Fix:** Use `threading.Lock()` around counter mutations, or use `threading.local()` for per-thread counters when multi-agent deployment is intended.

---

## 6. DESIGN — parse_mantra: Unknown Category Silently Discards Category

**Severity: LOW**

If a mantra file contains a `### Custom` heading (or any heading that isn't `global`, `project`, or `folder`), the parser continues and stores subsequent principles with `category=None`. No error is raised, no warning is logged.

**Verified by test:** `test_parse_mantra_unknown_category_silently_ignored` confirms category is silently dropped to `None`.

**Fix:** Either: (a) raise a `ValueError` for unknown categories, or (b) log a warning. Currently the principles are preserved but their category context is lost.

---

## 7. DESIGN — Web Server Writes to CWD

### Severity: LOW (local tool)

`web/server.py` always saves mantras to `Path.cwd() / ".mantrai.md"`. If the server is launched from a directory other than the project root (e.g., `~` or `/`), saved principles end up in the wrong place silently.

**Fix:** Resolve the correct project root using `_find_project_root()` before writing, same as `load_mantra()`.

---

## 8. Test Infrastructure — asyncio_mode Warning

### Severity: INFO

`pyproject.toml` sets `asyncio_mode = "auto"` but `pytest-asyncio` is not installed, producing a config warning on every test run:

```text
PytestConfigWarning: Unknown config option: asyncio_mode
```

### Fix

Either install `pytest-asyncio` or remove the option from `pyproject.toml`.

---

## 9. POSITIVE FINDINGS — What Works Well

These vectors were explicitly tested and held up cleanly:

| Vector | Result |
| -------- | -------- |
| SQL injection in all SessionTracker params | **Safe** — parameterized queries throughout |
| Path traversal in `load_mantra()` | **Safe** — raises exception, no silent read |
| XSS in web GUI save | **Safe** — stored as text, rendered via `escapeHtml()` |
| Pydantic schema validation (empty text, invalid level, empty list) | **Safe** — raises ValidationError |
| Concurrent SQLite writes (5 threads × 20 writes) | **Safe** — all 100 rows committed |
| Unicode/emoji in principles | **Safe** — parsed and rendered correctly |
| 1000-principle mantra | **Safe** — no performance cliff |
| SQL injection via session_id (DROP TABLE etc.) | **Safe** — table survives |
| Compliance window expiry (expired timestamps) | **Correct** — returns `False` |
| ActionGate strict always-inject | **Correct** |
| ActionGate off never-inject | **Correct** |
| Detector: all 3 strategies (env/state/context) | **Correct** |
| coordinate_injection: all 3 modes | **Correct** |
| MCP path traversal via `mantrai_validate_custom` | **Safe** — returns error, no data leak |
| Malformed JSON config (crash) | **BUG — see finding #3** |
| Self-mod bypass via `overwrite`/`remove` | **BUG — see finding #2** |

---

## 10. Coverage Summary — Before vs After

| Module | Before | After |
| -------- | -------- | ------- |
| `core/config.py` | 64% | **100%** |
| `core/detector.py` | 0% | **93%** |
| `core/schema.py` | 63% | **95%** |
| `session/tracker.py` | 86% | **100%** |
| `session/gate.py` | 100% | **100%** |
| `mcp_server/server.py` | 81% | **94%** |
| `web/server.py` | 0% | **93%** |
| `cli/main.py` | 47% | **73%** |
| `core/mantra.py` | 82% | **86%** |
| `core/selector.py` | 99% | **99%** |
| `mempalace_plugin` | 0% | **0%** (needs mempalace) |
| **TOTAL** | **60%** | **84%** |

---

## 11. Recommended Pre-Release Checklist

Priority order:

- [ ] **P1** Fix self-modification blocklist to include synonym verbs (finding #2)
- [ ] **P1** Add `try/except` around `json.load()` in `load_config()` (finding #3)
- [ ] **P2** Fix web server: read author from config, level from loaded mantra (finding #4)
- [ ] **P2** Fix web server: use `_find_project_root()` not `Path.cwd()` (finding #7)
- [ ] **P3** Add `threading.Lock` to `ActionGate.action_counter` (finding #5)
- [ ] **P3** Warn or raise on unknown category in `parse_mantra()` (finding #6)
- [ ] **P3** Remove or satisfy `asyncio_mode` in `pyproject.toml` (finding #8)
- [ ] **P3** Add `mempalace_plugin` exclusion to `.coveragerc`
- [ ] **P4** Add GitHub Actions CI (run `pytest` on push)
- [ ] **P4** Publish to PyPI
- [ ] **P4** Register in Anthropic MCP directory

---

## 12. Review of Previous Project Report

The original `docs/PROJECT_REPORT.md` is accurate in narrative but contains one factual error and one omission:

**Error:** Coverage stated as 69%; actual baseline was 60% (three modules omitted).

**Omission:** `core/detector.py` (the injection strategy/MemPalace detection module) is not mentioned in the architecture table, despite being a key runtime module.

**Accurate:** Architecture description, feature status matrix, CLI command inventory, MCP tool list, risk analysis, and top 5 recommendations are all correct and remain valid.
