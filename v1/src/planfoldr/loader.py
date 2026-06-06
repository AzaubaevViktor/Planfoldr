"""YAML loading and link resolution for Planfoldr scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import yaml
from pydantic import ValidationError

from planfoldr.schema import Cycle, PromptReference, Scenario


class SchemaLoadError(ValueError):
    """Validation error with file and YAML-path context."""

    def __init__(
        self,
        message: str,
        *,
        file_path: Path,
        yaml_path: str,
        expected: str,
        actual_preview: str,
    ) -> None:
        self.file_path = file_path
        self.yaml_path = yaml_path
        self.expected = expected
        self.actual_preview = actual_preview
        super().__init__(
            f"{file_path}: {message} at {yaml_path}; "
            f"expected {expected}; actual {actual_preview}"
        )


class LinkResolutionError(ValueError):
    """Raised when a linked YAML or prompt file cannot be resolved."""


@dataclass(frozen=True)
class LoadedPrompt:
    id: str
    path: Path
    content: str


@dataclass(frozen=True)
class LoadedCycle:
    document: Cycle
    path: Path
    prompts: Dict[str, LoadedPrompt]
    nested_cycles: List["LoadedCycle"]


@dataclass(frozen=True)
class LoadedScenario:
    document: Scenario
    path: Path
    cycles: List[LoadedCycle]


def load_scenario(path: str | Path) -> LoadedScenario:
    """Load a root scenario, linked cycle files and referenced prompt files."""

    scenario_path = Path(path).expanduser().resolve()
    raw = _read_yaml_mapping(scenario_path)
    scenario = _validate_yaml(Scenario, raw, scenario_path)
    cycles = [
        _load_cycle(_resolve_link(scenario_path.parent, cycle_ref.file), seen=())
        for cycle_ref in scenario.cycles
    ]
    return LoadedScenario(document=scenario, path=scenario_path, cycles=cycles)


def _load_cycle(path: Path, *, seen: Sequence[Path]) -> LoadedCycle:
    cycle_path = path.resolve()
    if cycle_path in seen:
        cycle_chain = " -> ".join(str(item) for item in [*seen, cycle_path])
        raise LinkResolutionError(f"Cycle link loop detected: {cycle_chain}")

    raw = _read_yaml_mapping(cycle_path)
    cycle = _validate_yaml(Cycle, raw, cycle_path)
    prompts = _load_prompts(cycle, cycle_path)
    nested = [
        _load_cycle(_resolve_link(cycle_path.parent, cycle_ref.file), seen=(*seen, cycle_path))
        for cycle_ref in cycle.nested_cycles
    ]
    return LoadedCycle(document=cycle, path=cycle_path, prompts=prompts, nested_cycles=nested)


def _load_prompts(cycle: Cycle, cycle_path: Path) -> Dict[str, LoadedPrompt]:
    prompts: Dict[str, LoadedPrompt] = {}
    for prompt in _iter_prompt_references(cycle):
        prompt_path = _resolve_link(cycle_path.parent, prompt.file)
        prompts[prompt.id] = LoadedPrompt(
            id=prompt.id,
            path=prompt_path,
            content=prompt_path.read_text(encoding="utf-8"),
        )
    return prompts


def _iter_prompt_references(cycle: Cycle) -> Iterable[PromptReference]:
    for task in cycle.tasks:
        if task.executor.prompt is not None:
            yield task.executor.prompt


def _read_yaml_mapping(path: Path) -> Mapping[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise LinkResolutionError(f"Linked file does not exist: {path}") from exc

    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SchemaLoadError(
            "Invalid YAML",
            file_path=path,
            yaml_path="$",
            expected="valid YAML mapping",
            actual_preview=_preview(str(exc)),
        ) from exc

    if not isinstance(loaded, Mapping):
        raise SchemaLoadError(
            "Invalid document root",
            file_path=path,
            yaml_path="$",
            expected="mapping",
            actual_preview=_preview(loaded),
        )
    return loaded


def _validate_yaml(model_type: type[Scenario] | type[Cycle], data: Mapping[str, Any], path: Path):
    try:
        return model_type.model_validate(data)
    except ValidationError as exc:
        error = exc.errors()[0]
        loc = tuple(error.get("loc", ()))
        yaml_path = _yaml_path(loc)
        expected = _expected_from_error(error)
        actual = _value_at_path(data, loc)
        raise SchemaLoadError(
            str(error.get("msg", "Validation error")),
            file_path=path,
            yaml_path=yaml_path,
            expected=expected,
            actual_preview=_preview(actual),
        ) from exc


def _resolve_link(base_dir: Path, link: str) -> Path:
    path = Path(link).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    resolved = path.resolve()
    if not resolved.exists():
        raise LinkResolutionError(f"Linked file does not exist: {resolved}")
    return resolved


def _yaml_path(loc: Tuple[Any, ...]) -> str:
    if not loc:
        return "$"
    path = "$"
    for part in loc:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}"
    return path


def _expected_from_error(error: Mapping[str, Any]) -> str:
    error_type = str(error.get("type", "valid value"))
    if error_type == "extra_forbidden":
        return "no unknown field"
    if error_type == "missing":
        return "required field"
    return str(error.get("msg", error_type))


def _value_at_path(data: Any, loc: Tuple[Any, ...]) -> Any:
    current = data
    for part in loc:
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        elif isinstance(current, list) and isinstance(part, int) and part < len(current):
            current = current[part]
        else:
            return "<missing>"
    return current


def _preview(value: Any) -> str:
    text = repr(value)
    if len(text) > 120:
        return text[:117] + "..."
    return text
