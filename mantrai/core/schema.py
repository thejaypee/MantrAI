from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Principle(BaseModel):
    text: str = Field(..., min_length=1, description="A single mantra principle")


class Mantra(BaseModel):
    header: str = "## Agent Mantra — Follow This At All Times"
    level: Literal["strict", "normal", "off"] = "normal"
    author: Optional[str] = None
    token: Optional[str] = None
    principles: List[Principle] = Field(default_factory=list, min_length=1)
    separator: str = "---"

    def render(self) -> str:
        lines = [self.header, ""]
        for p in self.principles:
            lines.append(f"> **{p.text}**")
        if self.level != "off":
            lines.append(f"> **MANTRA_LEVEL={self.level}.**")
        lines.append("")
        lines.append(self.separator)
        return "\n".join(lines)

    def to_markdown(self) -> str:
        frontmatter = []
        if self.level != "normal":
            frontmatter.append(f"**Level:** `{self.level}`")
        if self.author:
            frontmatter.append(f"**Author:** {self.author}")
        if self.token:
            frontmatter.append(f"**Token:** {self.token}")
        lines = []
        if frontmatter:
            lines.extend(frontmatter)
            lines.append("")
        lines.append(self.header)
        lines.append("")
        for p in self.principles:
            lines.append(f"> **{p.text}**")
        lines.append("")
        lines.append(self.separator)
        return "\n".join(lines)


class Confirmation(BaseModel):
    session_id: str
    timestamp: datetime
    agent_id: Optional[str] = None
    action_context: Optional[str] = None
    acknowledged: bool = True


class GateResult(BaseModel):
    require_reinjection: bool = False
    mantra_block: Optional[str] = None
    last_confirmed: Optional[Confirmation] = None
    action_count: int = 0
    threshold: int = 10
