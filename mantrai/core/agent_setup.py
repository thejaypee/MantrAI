from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional


def _settings_dir(target_dir: Optional[Path] = None, local_name: str = ".claude") -> Path:
    if target_dir:
        return target_dir / local_name
    local = Path.cwd() / local_name
    if local.exists() or (Path.cwd() / ".git").exists():
        return local
    return Path.home() / local_name


def detect_claude_code() -> bool:
    return shutil.which("claude") is not None or (Path.cwd() / ".claude").exists()


def detect_cursor() -> bool:
    return shutil.which("cursor") is not None or (Path.cwd() / ".cursor").exists()


def detect_codex() -> bool:
    return shutil.which("codex") is not None


def get_detected_agents() -> list[str]:
    agents = []
    if detect_claude_code():
        agents.append("claude-code")
    if detect_cursor():
        agents.append("cursor")
    if detect_codex():
        agents.append("codex")
    return agents


def install_claude_code_hook(target_dir: Optional[Path] = None) -> tuple[bool, str]:
    settings_dir = _settings_dir(target_dir, ".claude")
    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_file = settings_dir / "settings.json"

    config = {}
    if settings_file.exists():
        try:
            config = json.loads(settings_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False, f"Could not parse {settings_file}"

    config.setdefault("user-prompt-submit-hook", "mantrai hook")
    settings_file.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return True, f"Installed Claude Code hook in {settings_file}"


def install_cursor_mcp(target_dir: Optional[Path] = None) -> tuple[bool, str]:
    mcp_dir = _settings_dir(target_dir, ".cursor")
    mcp_dir.mkdir(parents=True, exist_ok=True)
    mcp_file = mcp_dir / "mcp.json"

    config = {}
    if mcp_file.exists():
        try:
            config = json.loads(mcp_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False, f"Could not parse {mcp_file}"

    config.setdefault("mcpServers", {})
    config["mcpServers"]["mantrai"] = {
        "command": "mantrai",
        "args": ["serve"]
    }
    mcp_file.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return True, f"Installed Cursor MCP config in {mcp_file}"
