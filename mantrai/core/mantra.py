from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

try:
    from importlib.resources import files
except ImportError:
    from importlib_resources import files  # type: ignore[no-redef]

from mantrai.core.schema import Mantra, Principle

DEFAULT_HEADER = "## Agent Mantra — Follow This At All Times"


def get_default_mantra() -> Mantra:
    return Mantra(
        level="strict",
        author="thejaypee",
        token="MANTRAI on Base — 0x89a83d8F5737325EAc5BdaF589FC6eCaE7E83BA3",
        principles=[
            # Global — All default principles are global. Project/Folder only exist if explicitly configured.
            Principle(text="ABSOLUTELY NO SIMULATIONS — Never fabricate test results, file contents, command output, or API responses. Run it or say you didn't.", category="global"),
            Principle(text="Never lie or trick — If uncertain, say so. Don't bluff. Don't pretend you read a file you didn't open.", category="global"),
            Principle(text="No changes that are not requested — Don't refactor 'while I'm here.' Don't add abstractions for a 2-line fix. Scope creep is a bug.", category="global"),
            Principle(text="Read before you write — Open the file before editing it. Stale context kills code.", category="global"),
            Principle(text="Thoroughly test before claiming success — 'All tests pass' means you ran them and saw green. Check stderr and exit codes.", category="global"),
            Principle(text="Stop one deployment before starting another — Don't stack ports. Don't leave zombie processes. Clean up before you start.", category="global"),
            Principle(text="Update ALL documentation — If the code changed, the docs changed. No exceptions. No lying in docs either.", category="global"),
            Principle(text="Security over convenience — Never disable verification flags, never hardcode secrets, never introduce injection vulnerabilities. Do it right or ask.", category="global"),
            Principle(text="Plan first — Start in plan mode. No code until the plan is written and approved.", category="global"),
            Principle(text="/init before acting — Read present documents. Confirm they match reality. Don't assume.", category="global"),
            Principle(text="Make plan and checklist if not present — Don't proceed without a written checklist.", category="global"),
            Principle(text="Confirm all checklist items with human — No silent completions. No marking your own homework.", category="global"),
            Principle(text="/build mode — Switch to build mode after plan approval.", category="global"),
            Principle(text="Fix EVERYTHING ALWAYS — Don't leave broken tests, lint errors, or TODOs behind.", category="global"),
            Principle(text="Interactive human demo — Show, don't tell. Let the human see it work.", category="global"),
            Principle(text="Wait for confirmation task is accomplished — The human closes the task, not you.", category="global"),
            Principle(text="Treat repositories as modules — Respect their boundaries. Don't edit vendor code.", category="global"),
            Principle(text="Follow the original repository's documentation — The author knows their software better than you.", category="global"),
            Principle(text="Build adapters or use .env files — Configure at the boundary, don't fork internals.", category="global"),
            Principle(text="File to mempalace — Document what happened so the next agent knows context wasn't lost.", category="global"),
        ],
    )


def _load_default_from_package() -> Optional[Mantra]:
    try:
        ref = files("mantrai").joinpath("mantras/default.md")
        if ref.is_file():
            content = ref.read_text(encoding="utf-8")
            return parse_mantra(content)
    except Exception:
        pass
    return None


def _find_project_root(start: Path = Path.cwd()) -> Optional[Path]:
    """Walk up from start looking for .git, pyproject.toml, or similar markers."""
    for parent in [start, *start.parents]:
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
            return parent
    return None


def _load_global_mantra() -> Optional[Mantra]:
    """Load global mantra from ~/.mantrai/mantra.md if it exists."""
    global_path = Path("~/.mantrai/mantra.md").expanduser()
    if global_path.exists():
        return parse_mantra(global_path.read_text(encoding="utf-8"))
    return None


def load_mantra(path: Optional[Path] = None) -> Mantra:
    if path is not None:
        content = path.read_text(encoding="utf-8")
        return parse_mantra(content)

    # 1. Folder-level: current directory
    folder = Path.cwd() / ".mantrai.md"
    if folder.exists():
        return parse_mantra(folder.read_text(encoding="utf-8"))

    # 2. Project-level: walk up to project root
    project_root = _find_project_root()
    if project_root is not None:
        project = project_root / ".mantrai.md"
        if project.exists():
            return parse_mantra(project.read_text(encoding="utf-8"))

    # 3. Global-level: ~/.mantrai/mantra.md
    global_mantra = _load_global_mantra()
    if global_mantra is not None:
        return global_mantra

    # 4. Bundled default
    pkg_mantra = _load_default_from_package()
    if pkg_mantra is not None:
        return pkg_mantra

    return get_default_mantra()


def parse_mantra(content: str) -> Mantra:
    lines = content.splitlines()
    level: str = "normal"
    author: Optional[str] = None
    token: Optional[str] = None
    principles: list[Principle] = []
    in_mantra_block = False
    current_category: Optional[str] = None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("**Level:**"):
            match = re.search(r"`?(strict|normal|off)`?", stripped)
            if match:
                level = match.group(1)
        elif stripped.startswith("**Author:**"):
            match = re.search(r"\*\*Author:\*\*\s*(.+)", stripped)
            if match:
                author = match.group(1).strip()
        elif stripped.startswith("**Token:**"):
            match = re.search(r"\*\*Token:\*\*\s*(.+)", stripped)
            if match:
                token = match.group(1).strip()
        elif stripped == DEFAULT_HEADER:
            in_mantra_block = True
            continue
        elif in_mantra_block and stripped == "---":
            break
        elif in_mantra_block and stripped.startswith("### "):
            cat_name = stripped[4:].strip().lower()
            if cat_name in ("global", "project", "folder"):
                current_category = cat_name
            else:
                import warnings
                warnings.warn(
                    f"Unknown mantra category '{cat_name}' — principles will have no category set.",
                    UserWarning,
                    stacklevel=2,
                )
            continue
        elif in_mantra_block and stripped.startswith("> **"):
            text = stripped[4:].strip("*")
            if text and not text.startswith("MANTRA_LEVEL"):
                principles.append(Principle(text=text, category=current_category))

    if not principles:
        raise ValueError("No principles found in mantra content")

    return Mantra(
        level=level,  # type: ignore[arg-type]
        author=author,
        token=token,
        principles=principles,
    )


def validate_mantra(content: str) -> tuple[bool, list[str]]:
    errors: list[str] = []
    lines = content.splitlines()
    header_count = sum(1 for line in lines if line.strip() == DEFAULT_HEADER)
    if header_count == 0:
        errors.append("Missing required mantra header")
    elif header_count > 1:
        errors.append(f"Header found {header_count} times; expected exactly once")

    principle_count = sum(
        1 for line in lines if re.match(r"^> \*\*[^*]+\*\*", line.strip()) and "MANTRA_LEVEL" not in line
    )
    if principle_count == 0:
        errors.append("No principles found (expected at least one '> **PRINCIPLE**' line)")

    in_block = False
    has_separator = False
    for line in lines:
        stripped = line.strip()
        if stripped == DEFAULT_HEADER:
            in_block = True
            continue
        if in_block and stripped == "---":
            has_separator = True
            break
    if not has_separator:
        errors.append("Missing '---' separator after mantra block")

    header_before = 0
    for line in lines:
        stripped = line.strip()
        if stripped == DEFAULT_HEADER:
            break
        if re.match(r"^#{1,6} ", stripped):
            header_before += 1
    if header_before > 0:
        errors.append(f"WARNING: {header_before} header(s) found before mantra block (will push it down)")

    return len(errors) == 0 or all("WARNING" in e for e in errors), errors


def render_mantra_block(mantra: Mantra) -> str:
    return mantra.render()
