"""Planfoldr runtime package."""

from planfoldr.context import ContextStore
from planfoldr.executors import ExecutorRegistry, OllamaModelAdapter, StubModelAdapter
from planfoldr.guards import BudgetTracker, PermissionEngine
from planfoldr.loader import LoadedScenario, SchemaLoadError, load_scenario
from planfoldr.runtime import Outcome, ScenarioResult, TaskResult, run_scenario

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
    "run_scenario",
]

__version__ = "0.1.0"
