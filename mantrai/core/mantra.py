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
        level="normal",
        author="thejaypee",
        token="MANTRAI on Base — 0x89a83d8F5737325EAc5BdaF589FC6eCaE7E83BA3",
        principles=[
            Principle(text="MAKE NO MISTAKES"),
            Principle(text="FIX EVERYTHING ALWAYS"),
            Principle(text="ALWAYS FOLLOW THE DOCUMENTATION OF THE REPOSITORY THE SOFTWARE MODULE CAME FROM"),
            Principle(text="NO CHANGES THAT ARE NOT REQUESTED"),
            Principle(text="STOP ONE DEPLOYMENT BEFORE STARTING ANOTHER"),
            Principle(text="MAKE SURE ALL IS THOROUGHLY TESTED AND COMPLETELY WORKING"),
            Principle(text="UPDATE ALL DOCUMENTATION"),
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


def load_mantra(path: Optional[Path] = None) -> Mantra:
    if path is None:
        # Check for local .mantrai.md in current directory
        local = Path.cwd() / ".mantrai.md"
        if local.exists():
            return parse_mantra(local.read_text(encoding="utf-8"))
        pkg_mantra = _load_default_from_package()
        if pkg_mantra is not None:
            return pkg_mantra
        return get_default_mantra()
    content = path.read_text(encoding="utf-8")
    return parse_mantra(content)


def parse_mantra(content: str) -> Mantra:
    lines = content.splitlines()
    level: str = "normal"
    author: Optional[str] = None
    token: Optional[str] = None
    principles: list[Principle] = []
    in_mantra_block = False

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
        elif in_mantra_block and stripped.startswith("> **"):
            text = stripped[4:].strip("*")
            if text and not text.startswith("MANTRA_LEVEL"):
                principles.append(Principle(text=text))

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
