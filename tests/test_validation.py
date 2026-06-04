from pathlib import Path

import pytest

from planfoldr.executors import ExecutorRegistry, StubModelAdapter
from planfoldr.guards import BudgetTracker, PermissionEngine
from planfoldr.loader import load_scenario
from planfoldr.runtime import run_scenario
from planfoldr.validation import OutputValidationError, validate_task_output


FIXTURES = Path(__file__).parent / "fixtures" / "scenarios"


def _registry(loaded, responses, retries: int) -> ExecutorRegistry:
    return ExecutorRegistry(
        permission_engine=PermissionEngine(loaded.document.constraints, base_dir=FIXTURES),
        budget_tracker=BudgetTracker(loaded.document.budgets),
        prompts=loaded.cycles[0].prompts,
        model_adapter=StubModelAdapter(responses),
        invalid_output_retries=retries,
    )


def test_validate_task_output_accepts_declared_schema() -> None:
    validate_task_output(
        {"status": "success", "items": []},
        {"type": "object", "required": ["status"], "properties": {"status": {"enum": ["success"]}}},
    )


def test_validate_task_output_rejects_missing_status() -> None:
    with pytest.raises(OutputValidationError) as exc_info:
        validate_task_output({}, {"type": "object"})

    assert exc_info.value.path == "$.status"


def test_model_output_retries_until_valid() -> None:
    loaded = load_scenario(FIXTURES / "validation_scenario.yaml")
    registry = _registry(
        loaded,
        {"validate_model:validation_prompt": [{"oops": True}, {"status": "success"}]},
        retries=1,
    )

    result = run_scenario(loaded, registry)

    assert result.status == "success"
    assert registry.budget_tracker.usage.model_calls == 2


def test_model_output_returns_retry_exceeded() -> None:
    loaded = load_scenario(FIXTURES / "validation_scenario.yaml")
    registry = _registry(
        loaded,
        {"validate_model:validation_prompt": [{"oops": True}, {"still": "bad"}]},
        retries=1,
    )

    result = run_scenario(loaded, registry)

    assert result.status == "failure"
    assert result.task_results[0].status == "retry_exceeded"
    assert result.task_results[0].evidence["status"] == "retry_exceeded"
