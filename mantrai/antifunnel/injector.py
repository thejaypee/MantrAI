from __future__ import annotations

from mantrai.core.schema import Mantra


class MantraInjector:
    def __init__(self, mantra: Mantra):
        self.mantra = mantra

    def inject(self) -> str:
        return self.mantra.render()

    def inject_with_level(self, level: str) -> str:
        m = self.mantra.model_copy(update={"level": level})
        return m.render()
