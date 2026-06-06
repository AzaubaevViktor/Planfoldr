"""Planfoldr runtime package."""

from planfoldr.context import ContextStore
from planfoldr.executors import ExecutorRegistry, OllamaModelAdapter, StubModelAdapter
from planfoldr.guards import BudgetTracker, PermissionEngine
from planfoldr.loader import LoadedScenario, SchemaLoadError, load_scenario
from planfoldr.runtime import Outcome, ScenarioResult, TaskResult, run_scenario
from planfoldr.trace import replay_task, run_and_trace
from planfoldr.validation import validate_task_output

__all__ = [
    "LoadedScenario",
    "ContextStore",
    "ExecutorRegistry",
    "BudgetTracker",
    "OllamaModelAdapter",
    "Outcome",
    "PermissionEngine",
    "StubModelAdapter",
    "ScenarioResult",
    "SchemaLoadError",
    "TaskResult",
    "__version__",
    "load_scenario",
    "replay_task",
    "run_and_trace",
    "run_scenario",
    "validate_task_output",
]

__version__ = "0.1.0"
