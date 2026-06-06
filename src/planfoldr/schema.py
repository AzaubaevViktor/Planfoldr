"""Pydantic schema objects for the Phase 2 scenario DSL.

These models intentionally mirror the YAML documents. Runtime execution will
use them later, but this module only describes shape and rejects ambiguity.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolsConstraint(StrictModel):
    allow: List[str]
    deny: List[str] = Field(default_factory=list)


class FilesystemConstraint(StrictModel):
    allow_read: List[str] = Field(default_factory=list)
    allow_write: List[str] = Field(default_factory=list)


class Constraints(StrictModel):
    tools: Optional[ToolsConstraint] = None
    filesystem: Optional[FilesystemConstraint] = None


class Budgets(StrictModel):
    max_iterations: Optional[int] = None
    max_tool_calls: Optional[int] = None
    max_model_calls: Optional[int] = None
    max_model_budget: Optional[float] = None
    max_model_tokens: Optional[int] = None
    max_model_cost_usd: Optional[float] = None
    max_cpu_time: Optional[int] = None
    max_ram: Optional[int] = None


class ContextPolicy(StrictModel):
    default_task_parent_read: bool
    default_task_parent_write: bool


class ContextAccess(StrictModel):
    read: List[str] = Field(default_factory=list)
    write: List[str] = Field(default_factory=list)
    delete: List[str] = Field(default_factory=list)


class RequiredCondition(StrictModel):
    id: str
    verifier_task: str


class ModelConfig(StrictModel):
    provider: str
    name: str


class RetryDefaults(StrictModel):
    invalid_output: int


class Defaults(StrictModel):
    model: Optional[ModelConfig] = None
    retry: Optional[RetryDefaults] = None


class PromptReference(StrictModel):
    id: str
    file: str


class Executor(StrictModel):
    kind: Literal["command", "model", "tool"]
    model: Optional[ModelConfig] = None
    prompt: Optional[PromptReference] = None
    tool: Optional[str] = None
    command: Optional[str] = None
    cwd: Optional[str] = None
    constraints: Optional[Constraints] = None


JsonSchema = Dict[str, Any]


class Task(StrictModel):
    id: str
    type: Literal["command", "model", "tool", "verify"]
    task: str
    input_schema: JsonSchema
    output_schema: JsonSchema
    executor: Executor


class CycleFileReference(StrictModel):
    file: str


class Cycle(StrictModel):
    id: str
    goal: str
    entrypoint: str
    tasks: List[Task]
    links: Dict[str, Dict[str, str]]
    nested_cycles: List[CycleFileReference] = Field(default_factory=list)
    budgets: Budgets
    constraints: Optional[Constraints] = None
    context_access: Optional[ContextAccess] = None


class Scenario(StrictModel):
    id: str
    goal: str
    required_conditions: List[RequiredCondition]
    constraints: Constraints
    budgets: Budgets
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    cycles: List[CycleFileReference]
    context_policy: ContextPolicy
    defaults: Optional[Defaults] = None
