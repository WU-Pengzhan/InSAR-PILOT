"""Shared command-plan model for queued shell work."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CommandPlan:
    label: str
    command: str
    cwd: str
    log_path: str
    step_name: str = ""
    is_generation: bool = False
    kind: str = "step"
    metadata: dict[str, Any] = field(default_factory=dict)
