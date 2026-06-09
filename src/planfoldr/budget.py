"""Budget (level 1).

Tracks and limits resource consumption at four scopes -- project / queue / ticket / cycle
-- and updates in real time as work happens (not at the end). On limit breach it performs a
**soft stop**: ongoing operations finish, no new ones start, and a ``budget.exceeded`` event
is emitted. It never hard-kills a process and never blocks audit logging.

PHASE_3 "Управление ресурсами и бюджетами" + PHASE_4 §9:
- commands: cpu_usage, ram_usage, command_runs
- files: file_changes, lines_added, lines_removed
- models: tokens_used, money_spent, api_requests, gpu_ram_hours
- general: queues_created, roles_created, tickets_created
- "Бюджет делегируется явно при порождении child-цикла"; child may not exceed without
  an explicit request_decision to the parent.
- ollama: only token counts come back from the provider; gpu_ram_hours is computed from
  ``ollama ps`` (SIZE x loaded-time, split by PROCESSOR), with correct attribution when two
  tickets share one model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Mapping, Optional

from planfoldr.audit import AuditLog, EventType


class Metric:
    # commands
    CPU_USAGE = "cpu_usage"
    RAM_USAGE = "ram_usage"
    COMMAND_RUNS = "command_runs"
    # files
    FILE_CHANGES = "file_changes"
    LINES_ADDED = "lines_added"
    LINES_REMOVED = "lines_removed"
    # models
    TOKENS = "tokens_used"
    MONEY = "money_spent"
    API_REQUESTS = "api_requests"
    GPU_RAM_HOURS = "gpu_ram_hours"
    # general
    QUEUES_CREATED = "queues_created"
    ROLES_CREATED = "roles_created"
    TICKETS_CREATED = "tickets_created"

    ALL = [
        CPU_USAGE, RAM_USAGE, COMMAND_RUNS,
        FILE_CHANGES, LINES_ADDED, LINES_REMOVED,
        TOKENS, MONEY, API_REQUESTS, GPU_RAM_HOURS,
        QUEUES_CREATED, ROLES_CREATED, TICKETS_CREATED,
    ]


class Budget:
    """A budget node. Consumption bubbles up to ancestors so a child cycle spends from the
    delegated slice *and* from the project total simultaneously."""

    def __init__(
        self,
        limits: Optional[Mapping[str, float]] = None,
        *,
        scope: str = "project",
        ticket_id: Optional[str] = None,
        audit: Optional[AuditLog] = None,
        parent: Optional["Budget"] = None,
    ) -> None:
        self.scope = scope
        self.ticket_id = ticket_id
        self.audit = audit
        self.parent = parent
        self.limits: Dict[str, float] = {k: float(v) for k, v in (limits or {}).items()}
        self.usage: Dict[str, float] = {metric: 0.0 for metric in Metric.ALL}
        self.exceeded = False
        self._exceeded_resources: set[str] = set()

    # -- consumption ----------------------------------------------------------
    def consume(self, metric: str, amount: float = 1.0) -> bool:
        """Record usage in real time. Returns True if still within limits, False if this
        consumption crossed a limit at any scope (caller should finish-but-not-start-new)."""
        ok = True
        node: Optional[Budget] = self
        while node is not None:
            node.usage[metric] = node.usage.get(metric, 0.0) + amount
            if node._check_over(metric):
                ok = False
            node = node.parent
        return ok

    def _check_over(self, metric: str) -> bool:
        limit = self.limits.get(metric)
        if limit is None:
            return False
        over = self.usage[metric] > limit
        if over and metric not in self._exceeded_resources:
            self._exceeded_resources.add(metric)
            self.exceeded = True
            if self.audit is not None:
                self.audit.emit(
                    EventType.BUDGET_EXCEEDED,
                    ticket_id=self.ticket_id,
                    scope=self.scope,
                    resource=metric,
                    limit=limit,
                    used=self.usage[metric],
                )
        return over

    # -- soft stop ------------------------------------------------------------
    @property
    def blocked(self) -> bool:
        """True if this node or any ancestor has exceeded a limit (soft stop)."""
        node: Optional[Budget] = self
        while node is not None:
            if node.exceeded:
                return True
            node = node.parent
        return False

    def can_start_new(self) -> bool:
        return not self.blocked

    # -- delegation -----------------------------------------------------------
    def delegate(
        self,
        limits: Mapping[str, float],
        *,
        scope: str,
        ticket_id: Optional[str] = None,
    ) -> "Budget":
        child = Budget(limits, scope=scope, ticket_id=ticket_id, audit=self.audit, parent=self)
        if self.audit is not None:
            self.audit.emit(
                EventType.BUDGET_DELEGATED,
                ticket_id=ticket_id,
                scope=scope,
                parent_scope=self.scope,
                limits=dict(limits),
            )
        return child

    def request_increase(self, metric: str, extra: float, *, approved: bool) -> bool:
        """A child cannot raise its own limit silently -- only via an approved request_decision
        to the parent (PHASE_4 Cycle↔Budget §3.2)."""
        if not approved:
            return False
        self.limits[metric] = self.limits.get(metric, 0.0) + float(extra)
        self._exceeded_resources.discard(metric)
        self.exceeded = bool(self._exceeded_resources)
        return True

    # -- ollama gpu metering --------------------------------------------------
    def charge_model_seconds(
        self,
        model: str,
        seconds: float,
        *,
        ps_text: Optional[str] = None,
        ps_provider: Optional[Callable[[], str]] = None,
    ) -> float:
        """Charge gpu_ram_hours for `seconds` of `model` runtime. Per-call charging means two
        tickets sharing a loaded model are attributed independently by their own durations."""
        text = ps_text if ps_text is not None else (ps_provider() if ps_provider else "")
        info = parse_ollama_ps(text).get(model, {})
        size_gb = float(info.get("size_gb", 0.0))
        gpu_fraction = float(info.get("gpu_fraction", 1.0))
        gpu_ram_hours = size_gb * gpu_fraction * (seconds / 3600.0)
        if gpu_ram_hours:
            self.consume(Metric.GPU_RAM_HOURS, gpu_ram_hours)
        return gpu_ram_hours

    # -- serialization --------------------------------------------------------
    def snapshot(self) -> Dict[str, float]:
        return dict(self.usage)

    def to_dict(self) -> Dict[str, object]:
        return {
            "scope": self.scope,
            "ticket_id": self.ticket_id,
            "limits": dict(self.limits),
            "usage": dict(self.usage),
            "exceeded": self.exceeded,
            "exceeded_resources": sorted(self._exceeded_resources),
        }


_SIZE_RE = re.compile(r"([\d.]+)\s*(TB|GB|MB|KB|B)", re.IGNORECASE)
_UNIT_GB = {"TB": 1024.0, "GB": 1.0, "MB": 1 / 1024.0, "KB": 1 / (1024.0 * 1024.0), "B": 1 / (1024.0 ** 3)}


def parse_ollama_ps(text: str) -> Dict[str, Dict[str, float]]:
    """Parse `ollama ps` into {model_name: {size_gb, gpu_fraction}}.

    Columns: NAME  ID  SIZE  PROCESSOR  CONTEXT  UNTIL. PROCESSOR looks like
    "100% GPU", "100% CPU" or "30%/70% CPU/GPU".
    """
    result: Dict[str, Dict[str, float]] = {}
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("NAME"):
            continue
        cols = re.split(r"\s{2,}", line.strip())
        if len(cols) < 4:
            continue
        name = cols[0]
        size_gb = _parse_size_gb(cols[2])
        gpu_fraction = _parse_gpu_fraction(cols[3])
        result[name] = {"size_gb": size_gb, "gpu_fraction": gpu_fraction}
    return result


def _parse_size_gb(value: str) -> float:
    match = _SIZE_RE.search(value)
    if not match:
        return 0.0
    return float(match.group(1)) * _UNIT_GB[match.group(2).upper()]


def _parse_gpu_fraction(processor: str) -> float:
    percents = [int(p) for p in re.findall(r"(\d+)%", processor)]
    labels = re.findall(r"(CPU|GPU)", processor.upper())
    if not percents or not labels:
        return 1.0
    paired = dict(zip(labels, percents))
    if "GPU" in paired:
        return paired["GPU"] / 100.0
    if "CPU" in paired:
        return 0.0
    return 1.0
