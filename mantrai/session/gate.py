from __future__ import annotations

import threading
from typing import Optional

from mantrai.core.config import load_config
from mantrai.core.schema import GateResult, Mantra
from mantrai.session.tracker import SessionTracker


class ActionGate:
    def __init__(
        self,
        tracker: SessionTracker,
        mantra: Mantra,
        level: Optional[str] = None,
        config: Optional[dict] = None,
    ):
        self.tracker = tracker
        self.mantra = mantra
        self.level = level or mantra.level
        self._action_counter = 0
        self._lock = threading.Lock()

        cfg = config or load_config()
        self.threshold = (
            cfg.get("strict_threshold", 1)
            if self.level == "strict"
            else cfg.get("normal_threshold", 5)
        )
        self.window_minutes = cfg.get("compliance_window_minutes", 5)

    @property
    def action_counter(self) -> int:
        with self._lock:
            return self._action_counter

    @action_counter.setter
    def action_counter(self, value: int) -> None:
        with self._lock:
            self._action_counter = value

    def before_action(self, action_name: str, session_id: str) -> GateResult:
        is_diagnostic = action_name in ("cli_check", "mcp_check")
        is_forced = action_name == "forced_injection"

        if not is_diagnostic:
            self.action_counter += 1

        last = self.tracker.last_confirmation(session_id)
        in_window = (
            self.tracker.compliance_window(session_id, self.window_minutes)
            if last
            else False
        )

        if self.level == "off":
            return GateResult(
                require_reinjection=False,
                action_count=self.action_counter,
                threshold=self.threshold,
                last_confirmed=last,
            )

        if self.level == "strict" or is_forced:
            if is_forced:
                self.action_counter = 0
            return GateResult(
                require_reinjection=True,
                mantra_block=self.mantra.render(),
                last_confirmed=last,
                action_count=self.action_counter,
                threshold=self.threshold,
            )

        # normal level
        if self.action_counter >= self.threshold or not in_window:
            self.action_counter = 0
            return GateResult(
                require_reinjection=True,
                mantra_block=self.mantra.render(),
                last_confirmed=last,
                action_count=self.action_counter,
                threshold=self.threshold,
            )

        return GateResult(
            require_reinjection=False,
            action_count=self.action_counter,
            threshold=self.threshold,
            last_confirmed=last,
        )

    def reset_counter(self) -> None:
        self.action_counter = 0
