"""Public-demo switches from environment. Both default to off."""

from __future__ import annotations

import os
from dataclasses import dataclass

_TRUE = {"1", "true", "yes", "on"}


def _flag(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in _TRUE


@dataclass(frozen=True, slots=True)
class DemoSettings:
    """``DEMO_MODE`` gates every destructive demo operation."""

    demo_mode: bool = False
    reset_on_start: bool = False

    @classmethod
    def from_env(cls) -> DemoSettings:
        return cls(
            demo_mode=_flag("DEMO_MODE"),
            reset_on_start=_flag("DEMO_RESET_ON_START"),
        )

    @property
    def should_reset_on_start(self) -> bool:
        return self.demo_mode and self.reset_on_start
