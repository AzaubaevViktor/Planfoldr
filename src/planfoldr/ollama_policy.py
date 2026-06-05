"""Ollama model selection policy for local demo runs."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Iterable, Optional


MAX_DEMO_MODEL_GB = 12.0
MAX_DEMO_MODEL_B = 12.0


@dataclass(frozen=True)
class OllamaModelCandidate:
    name: str
    model_id: str = ""
    size: str = ""
    size_gb: Optional[float] = None
    parameter_b: Optional[float] = None
    accepted: bool = False
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "id": self.model_id,
            "size": self.size,
            "size_gb": self.size_gb,
            "parameter_b": self.parameter_b,
            "accepted": self.accepted,
            "reason": self.reason,
        }


def list_installed_ollama_models() -> list[OllamaModelCandidate]:
    completed = subprocess.run(
        ["ollama", "list"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "ollama list failed").strip())
    return parse_ollama_list(completed.stdout)


def parse_ollama_list(output: str) -> list[OllamaModelCandidate]:
    candidates: list[OllamaModelCandidate] = []
    for line in output.splitlines():
        if not line.strip() or line.lstrip().startswith("NAME"):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        name = parts[0]
        model_id = parts[1]
        size = f"{parts[2]} {parts[3]}"
        candidates.append(classify_ollama_model(name=name, model_id=model_id, size=size))
    return candidates


def classify_ollama_model(name: str, *, model_id: str = "", size: str = "") -> OllamaModelCandidate:
    size_gb = _parse_size_gb(size)
    parameter_b = infer_parameter_b(name)
    reasons: list[str] = []
    accepted = True
    if parameter_b is not None and parameter_b > MAX_DEMO_MODEL_B:
        accepted = False
        reasons.append(f"parameter hint {parameter_b:g}B exceeds {MAX_DEMO_MODEL_B:g}B")
    if size_gb is not None and size_gb > MAX_DEMO_MODEL_GB:
        accepted = False
        reasons.append(f"installed size {size_gb:g} GB exceeds {MAX_DEMO_MODEL_GB:g} GB")
    if accepted:
        hints: list[str] = []
        if parameter_b is not None:
            hints.append(f"parameter hint {parameter_b:g}B")
        else:
            hints.append("no parameter hint")
        if size_gb is not None:
            hints.append(f"installed size {size_gb:g} GB")
        else:
            hints.append("unknown installed size")
        reasons.append("accepted: " + ", ".join(hints))
    return OllamaModelCandidate(
        name=name,
        model_id=model_id,
        size=size,
        size_gb=size_gb,
        parameter_b=parameter_b,
        accepted=accepted,
        reason="; ".join(reasons),
    )


def eligible_ollama_models(candidates: Iterable[OllamaModelCandidate]) -> list[OllamaModelCandidate]:
    return [candidate for candidate in candidates if candidate.accepted]


def validate_ollama_model_name(model_name: str) -> None:
    parameter_b = infer_parameter_b(model_name)
    if parameter_b is not None and parameter_b > MAX_DEMO_MODEL_B:
        raise ValueError(
            f"Ollama model '{model_name}' appears to be {parameter_b:g}B, "
            f"above the Planfoldr demo limit of {MAX_DEMO_MODEL_B:g}B"
        )


def infer_parameter_b(model_name: str) -> Optional[float]:
    matches = re.findall(r"(?<![a-z0-9])(\d+(?:\.\d+)?)\s*b(?![a-z])", model_name.lower())
    if not matches:
        return None
    return max(float(value) for value in matches)


def _parse_size_gb(size: str) -> Optional[float]:
    match = re.search(r"(\d+(?:\.\d+)?)\s*([kmgt]b)", size.lower())
    if match is None:
        return None
    value = float(match.group(1))
    unit = match.group(2)
    if unit == "kb":
        return value / (1024 * 1024)
    if unit == "mb":
        return value / 1024
    if unit == "gb":
        return value
    if unit == "tb":
        return value * 1024
    return None
