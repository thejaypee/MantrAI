from __future__ import annotations

from typing import Optional

from mantrai.core.schema import GateResult, Mantra
from mantrai.session.tracker import SessionTracker


class ActionGate:
    def __init__(
        self,
        tracker: SessionTracker,
        mantra: Mantra,
        level: Optional[str] = None,
    ):
        self.tracker = tracker
        self.mantra = mantra
        self.level = level or mantra.level
        self.action_counter = 0
        self.threshold = 1 if self.level == "strict" else 5
        self.window_minutes = 5

    def before_action(self, action_name: str, session_id: str) -> GateResult:
        self.action_counter += 1
        last = self.tracker.last_confirmation(session_id)
        in_window = self.tracker.compliance_window(session_id, self.window_minutes) if last else False

        if self.level == "off":
            return GateResult(
                require_reinjection=False,
                action_count=self.action_counter,
                threshold=self.threshold,
                last_confirmed=last,
            )

        if self.level == "strict":
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
