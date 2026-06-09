"""Scenario (level 7).

The entry point: a human's plain-text task plus budget, accesses and verification. From the plain
text the top cycle formulates concrete goals/constraints (Context Exploration). A scenario is
immutable after launch and does not describe the full task graph -- only the starting point.

PHASE_3 "Сценарий" + PHASE_4 §13.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from planfoldr.budget import Metric

# Friendly aliases accepted in scenario YAML → canonical budget metric keys.
_BUDGET_ALIASES = {
    "tokens": Metric.TOKENS,
    "money": Metric.MONEY,
    "requests": Metric.API_REQUESTS,
    "commands": Metric.COMMAND_RUNS,
    "tickets": Metric.TICKETS_CREATED,
    "gpu_ram_hours": Metric.GPU_RAM_HOURS,
}


@dataclass(frozen=True)
class ModelSettings:
    provider: str = "ollama"
    name: str = "gemma4:26b-mlx"
    parameter_count: float = 26e9
    cost_per_token: float = 0.0
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Scenario:
    goal_text: str
    budget: Dict[str, float] = field(default_factory=dict)
    accesses: List[Dict[str, Any]] = field(default_factory=list)
    verification_commands: List[str] = field(default_factory=list)
    verification_criteria: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    model: ModelSettings = field(default_factory=ModelSettings)
    name: str = "scenario"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "goal_text": self.goal_text,
            "budget": dict(self.budget),
            "accesses": list(self.accesses),
            "verification": {"commands": list(self.verification_commands), "criteria": list(self.verification_criteria)},
            "constraints": list(self.constraints),
            "model": {"provider": self.model.provider, "name": self.model.name,
                      "parameter_count": self.model.parameter_count},
        }


def _normalize_budget(raw: Optional[Dict[str, Any]]) -> Dict[str, float]:
    budget: Dict[str, float] = {}
    for key, value in (raw or {}).items():
        budget[_BUDGET_ALIASES.get(key, key)] = float(value)
    return budget


def load_scenario(path: Path | str) -> Scenario:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    verification = data.get("verification", {}) or {}
    model = data.get("model", {}) or {}
    return Scenario(
        name=str(data.get("name", Path(path).stem)),
        goal_text=str(data.get("goal") or data.get("goal_text") or ""),
        budget=_normalize_budget(data.get("budget")),
        accesses=list(data.get("accesses", [])),
        verification_commands=list(verification.get("commands", [])),
        verification_criteria=list(verification.get("criteria", [])),
        constraints=list(data.get("constraints", [])),
        model=ModelSettings(
            provider=str(model.get("provider", "ollama")),
            name=str(model.get("name", "gemma4:26b-mlx")),
            parameter_count=float(model.get("parameter_count", 26e9)),
            cost_per_token=float(model.get("cost_per_token", 0.0)),
            options=dict(model.get("options", {})),
        ),
    )
