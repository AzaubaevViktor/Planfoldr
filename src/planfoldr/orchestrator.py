"""Orchestrator + runtime (level 7).

Wires every entity into a runnable system: from a Scenario it spins up the audit log, project
budget, ticket graph, role/queue registries, score system, knowledge base, model registry and
birthgiver; seeds the base queues; runs the top decomposition cycle; drives the executor loop
(triage → select model → run cycle → resolve dependencies); soft-stops on budget; and runs the
final scenario verification gate. Everything is observable through the audit log + stream sink.

PHASE_3 "Флоу работы" (Steps 1-9) + PHASE_4 Quest 5.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from planfoldr.audit import AuditLog, EventType
from planfoldr.birthgiver import Birthgiver, Human, QueueRegistry, RoleRegistry, handle_create_role
from planfoldr.budget import Budget, Metric
from planfoldr.cycle import Cycle
from planfoldr.graph import TicketGraph
from planfoldr.knowledge_base import KnowledgeBase
from planfoldr.model import ModelAdapter, ModelConfig, ModelRegistry, OllamaModel
from planfoldr.queue import Queue
from planfoldr.role import Executor, QueueManager
from planfoldr.scenario import Scenario
from planfoldr.score import ScoreSystem
from planfoldr.ticket import TERMINAL, Check, Status, Ticket, new_ticket
from planfoldr.toolset import ToolRegistry, Toolset
from planfoldr.tools_impl import register_default_tools
from planfoldr.util import new_id


# Base role seed: domain tools + the ticket types each may create.
BASE_ROLES: Dict[str, Dict[str, Any]] = {
    "orchestration": {
        "domain": [],
        "prompt": ("You are the orchestrator. Break the goal into the MINIMAL set of tickets via "
                   "create_ticket — often a single code ticket, plus a tests ticket only if useful. "
                   "Give each ticket a concrete goal and command checks. NEVER create duplicate "
                   "tickets for the same work. Once the tickets are created, respond with finish."),
        "can_create": ["*"],  # the top planner may create any ticket type; unknown types summon birthgiver
    },
    "developer": {
        "domain": ["file_edit", "bash"], "prompt": "You are a developer. Write code and tests in the workspace.",
        "can_create": ["tests", "fix", "security-review", "research"],
    },
    "research": {
        "domain": ["bash", "file_edit"], "prompt": "You are a researcher. Investigate and document findings.",
        "can_create": ["documentation", "fix"],
    },
    "verification": {
        "domain": ["bash"], "prompt": "You are a verifier. Run checks and confirm evidence.",
        "can_create": ["fix"],
    },
    "security": {
        "domain": ["bash", "file_edit"], "prompt": "You are security. Find and block vulnerabilities.",
        "can_create": ["fix", "block"],
    },
}

TYPE_TO_QUEUE = {
    "code": "developer", "tests": "developer", "fix": "developer", "refactor": "developer",
    "research": "research", "documentation": "research",
    "verify": "verification", "benchmark": "verification",
    "security-review": "security", "audit": "security", "block": "security",
    "plan": "orchestration", "decompose": "orchestration", "orchestration": "orchestration",
    "create_role": "birthgiver",
}

DEFAULT_TICKET_BUDGET = {Metric.TOKENS: 40_000}


@dataclass
class RunResult:
    run_id: str
    run_dir: str
    status: str
    scenario: Dict[str, Any]
    tickets: Dict[str, str]
    budget: Dict[str, float]
    scores: Dict[str, Any]
    audit_path: str
    cycles_run: int = 0
    reason: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id, "run_dir": self.run_dir, "status": self.status,
            "scenario": self.scenario, "tickets": self.tickets, "budget": self.budget,
            "scores": self.scores, "audit_path": self.audit_path, "cycles_run": self.cycles_run,
            "reason": self.reason, **self.extra,
        }


class Orchestrator:
    def __init__(
        self,
        scenario: Scenario,
        *,
        runs_dir: Path | str = "runs",
        run_id: Optional[str] = None,
        model_adapter: Optional[ModelAdapter] = None,
        human: Optional[Human] = None,
        stream_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
        max_cycles: int = 40,
    ) -> None:
        self.scenario = scenario
        self.run_id = run_id or new_id("run")
        self.run_dir = Path(runs_dir) / self.run_id
        self.workspace = self.run_dir / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.audit = AuditLog(self.run_dir / "audit.jsonl")
        from planfoldr.visibility.events import VisibilityState
        self.vis = VisibilityState()

        self._model_io_path = self.run_dir / "model_io.jsonl"

        def _sink(event: Dict[str, Any]) -> None:
            # Every run feeds an internal Visibility state (for the static report) plus any
            # user-supplied sink (terminal / live web server). Observation never breaks the run.
            try:
                self.vis.ingest(event)
            except Exception:  # noqa: BLE001
                pass
            if event.get("event") == "model_output":
                self._record_model_io(event)
            if stream_sink is not None:
                stream_sink(event)

        self.audit.subscribe(lambda e: _sink({"event": "audit", **e.to_dict()}))
        self.stream_sink = _sink
        self.ticket_budgets: Dict[str, Budget] = {}
        self._status = "running"
        self.budget = Budget(scenario.budget, scope="project", audit=self.audit)
        self.graph = TicketGraph(self.audit)
        self.kb = KnowledgeBase(self.audit)
        self.score = ScoreSystem(self.audit)
        self.tool_registry = register_default_tools(ToolRegistry())
        self.tool_registry.bind("create_role", handle_create_role)
        self.role_registry = RoleRegistry()
        self.queue_registry = QueueRegistry()
        self.birthgiver = Birthgiver(tool_registry=self.tool_registry, role_registry=self.role_registry,
                                     queue_registry=self.queue_registry, audit=self.audit, graph=self.graph)
        self.role_registry.register(self.birthgiver)
        self.human = human or Human(default="proceed", audit=self.audit)
        self.max_cycles = max_cycles
        self.tickets: Dict[str, Ticket] = {}
        self._counters: Dict[str, int] = {}
        self._ticket_index: Dict[tuple, str] = {}  # (type, normalized goal) → id, for dedup
        self.cycles_run = 0

        # Model registry (provider-aware). The runtime selects; the model never selects itself.
        self.model_registry = ModelRegistry()
        cfg = ModelConfig(id=scenario.model.name, provider=scenario.model.provider,
                          parameter_count=scenario.model.parameter_count,
                          cost_per_token=scenario.model.cost_per_token, options=scenario.model.options)
        adapter = model_adapter or OllamaModel(scenario.model.name, options=scenario.model.options)
        self.model_registry.register(cfg, adapter)
        self.ps_provider = _ollama_ps if scenario.model.provider == "ollama" else None

        self._allowed_paths = self._resolve_accesses()

    # -- run ------------------------------------------------------------------
    def run(self) -> RunResult:
        self.audit.emit(EventType.SCENARIO_STARTED, scenario=self.scenario.name, goal=self.scenario.goal_text,
                        budget=dict(self.scenario.budget))
        self._seed_base_queues()
        self._write_report()  # HTML report exists from the very start of the run
        self._run_top_cycle()
        self._executor_loop()
        status, reason = self._final_verification()
        self._status = status
        self.audit.emit(EventType.SCENARIO_COMPLETED, scenario=self.scenario.name, status=status, reason=reason)
        result = RunResult(
            run_id=self.run_id, run_dir=str(self.run_dir), status=status, scenario=self.scenario.to_dict(),
            tickets={tid: t.status for tid, t in self.tickets.items()}, budget=self.budget.snapshot(),
            scores=self.score.to_dict(), audit_path=str(self.run_dir / "audit.jsonl"),
            cycles_run=self.cycles_run, reason=reason,
        )
        self._persist(result)
        return result

    # -- setup ----------------------------------------------------------------
    def _seed_base_queues(self) -> None:
        for name, spec in BASE_ROLES.items():
            manager = QueueManager(f"{name}-manager", prompt=f"You manage the {name} queue.",
                                   toolset=Toolset([], registry=self.tool_registry), queue_id=name)
            role_id = "orchestrator" if name == "orchestration" else f"{name}-exec"
            executor = Executor(role_id, prompt=spec["prompt"],
                                toolset=Toolset(spec["domain"], registry=self.tool_registry),
                                can_create_ticket_types=spec["can_create"])
            queue = Queue(id=name, name=name, graph=self.graph, audit=self.audit,
                          manager_role=manager.id, executor_roles=[executor.id])
            self.role_registry.register(manager)
            self.role_registry.register(executor)
            self.queue_registry.register(queue)
            self.audit.emit(EventType.QUEUE_CREATED, actor="birthgiver", queue=name,
                            roles=[manager.id, executor.id], seed=True)
        # The birthgiver gets its own queue so summoned create_role tickets are processed live.
        bg_queue = Queue(id="birthgiver", name="birthgiver", graph=self.graph, audit=self.audit,
                         manager_role="birthgiver", executor_roles=["birthgiver"],
                         description="role/queue creation requests")
        self.queue_registry.register(bg_queue)

    def _resolve_accesses(self) -> List[Path]:
        roots = [self.workspace.resolve()]
        for access in self.scenario.accesses:
            raw = str(access.get("path", "."))
            # Scenario paths are rendered against the per-run workspace for isolation.
            roots.append((self.workspace / Path(raw).name).resolve() if not Path(raw).is_absolute() else Path(raw).resolve())
        return roots

    # -- top cycle ------------------------------------------------------------
    def _run_top_cycle(self) -> None:
        top = new_ticket("orchestration-0", title="decompose scenario", type="orchestration",
                         goal=self.scenario.goal_text, created_by="human", role="orchestrator",
                         queue="orchestration", audit=self.audit)
        top.metadata["constraints"] = list(self.scenario.constraints)
        self.tickets[top.id] = top
        self.graph.add_ticket(top)
        top.transition(Status.READY, actor="human", audit=self.audit)
        top.transition(Status.RUNNING, actor="human", audit=self.audit)
        self._run_cycle(top, "orchestration")

    # -- executor loop --------------------------------------------------------
    def _executor_loop(self) -> None:
        while self.cycles_run < self.max_cycles:
            self._triage_all()
            self._refresh_all()
            if self.budget.blocked:
                self.audit.emit(EventType.BUDGET_EXCEEDED, scope="project", note="soft stop: no new cycles")
                break
            picked = self._next_ready()
            if picked is None:
                break
            self._run_executor_cycle(*picked)
            self._refresh_all()

    def _triage_all(self) -> None:
        for queue in self.queue_registry.queues.values():
            for ticket in list(queue.incoming()):
                # Deterministic manager triage: accept into the queue (priority by intake order).
                queue.accept(ticket.id, priority=ticket.priority, actor=f"{queue.id}-manager")

    def _refresh_all(self) -> None:
        for queue in self.queue_registry.queues.values():
            queue.refresh_ready()

    def _next_ready(self) -> Optional[tuple[Queue, Ticket]]:
        best: Optional[tuple[Queue, Ticket]] = None
        for queue in self.queue_registry.queues.values():
            ticket = queue.get_next()
            if ticket is None:
                continue
            if best is None or ticket.priority > best[1].priority:
                best = (queue, ticket)
        return best

    def _run_executor_cycle(self, queue: Queue, ticket: Ticket) -> None:
        if ticket.type == "create_role":
            self._run_birthgiver(ticket)
            return
        executor = self.role_registry.get(queue.executor_roles[0])
        while True:
            ticket.transition(Status.RUNNING, actor=executor.id, audit=self.audit)
            model_cfg = self.model_registry.select(executor.id, ticket.type, self.score) or self.model_registry.config_for(
                self.scenario.model.name)
            self.audit.emit(EventType.TICKET_ASSIGNED, ticket_id=ticket.id, role=executor.id, model=model_cfg.id)
            result = self._run_cycle(ticket, queue.id, role=executor, model_cfg=model_cfg)
            self.cycles_run += 1
            if result.status == Status.NEEDS_REVIEW and not ticket.exhausted_attempts() and self.cycles_run < self.max_cycles:
                continue  # re-attempt until verified or attempts exhausted
            break

    def _run_birthgiver(self, ticket: Ticket) -> None:
        """Process a summoned create_role ticket: the birthgiver links/creates the role + queue live."""
        ticket.transition(Status.RUNNING, actor="birthgiver", audit=self.audit)
        name = ticket.metadata.get("requested_role") or ticket.title
        decision = self.birthgiver.link_or_create(
            name, needed=True, prompt=f"You are the {name}.",
            domain_tools=["file_edit", "bash"], can_create_ticket_types=["fix"],
            budget_scope={Metric.TOKENS: 30_000},
        )
        ticket.add_evidence(check_index=None, status="success", proof=f"birthgiver {decision.action} role '{name}'")
        ticket.transition(Status.DONE, actor="birthgiver", audit=self.audit, proof=f"role {decision.action}: {name}")
        self.cycles_run += 1
        self._write_report()

    def _run_cycle(self, ticket: Ticket, queue_id: str, *, role=None, model_cfg=None):
        role = role or self.role_registry.get("orchestrator")
        model_cfg = model_cfg or self.model_registry.config_for(self.scenario.model.name)
        adapter = self.model_registry.adapter_for(model_cfg.id)
        ticket_budget = self.budget.delegate(ticket.budget or dict(DEFAULT_TICKET_BUDGET), scope="ticket", ticket_id=ticket.id)
        self.ticket_budgets[ticket.id] = ticket_budget
        cycle = Cycle(
            ticket=ticket, role=role, model_config=model_cfg, model_adapter=adapter, budget=ticket_budget,
            audit=self.audit, toolset=role.effective_toolset(queue_id), workspace=self.workspace,
            graph=self.graph, knowledge_base=self.kb, score_system=self.score,
            allowed_paths=self._allowed_paths, on_create_ticket=self._create_ticket,
            on_request_decision=self.human, on_summon=self._on_summon,
            stream_sink=self.stream_sink, ps_provider=self.ps_provider, report_hook=self._write_report,
        )
        result = cycle.run()
        self._write_report()
        return result

    # -- create_ticket routing ------------------------------------------------
    def _create_ticket(self, spec: Dict[str, Any]) -> str:
        ttype = spec.get("type") or spec.get("ticket_type") or "code"
        queue_id = TYPE_TO_QUEUE.get(ttype)
        if queue_id is None or not self.queue_registry.has(queue_id):
            # Unknown specialization → summon birthgiver (registered + processed live), route work to developer.
            summon = self.birthgiver.summon_ticket(ttype, requester=spec.get("created_by", "orchestrator"))
            self._register_ticket(summon)
            queue_id = "developer"
        n = self._counters.get(queue_id, 0) + 1
        self._counters[queue_id] = n
        tid = spec.get("id") or f"{queue_id}-{n}"
        # Local models phrase the goal in different fields -- accept the common aliases.
        goal = (spec.get("goal") or spec.get("description") or spec.get("summary")
                or spec.get("task") or spec.get("title") or "")
        # Deduplicate: a near-identical (type, goal) that is still open returns the existing ticket
        # instead of spawning a duplicate (local models tend to re-create the same ticket).
        dedup_key = (ttype, " ".join(goal.lower().split())[:80])
        existing = self._ticket_index.get(dedup_key)
        if existing and self.tickets.get(existing) and self.tickets[existing].status not in TERMINAL:
            return existing
        title = spec.get("title") or (goal[:60] if goal else tid)
        raw_checks = spec.get("checks") or spec.get("verification") or spec.get("tests") or []
        checks = [c if isinstance(c, Check) else (Check.from_dict(c) if isinstance(c, dict)
                  else Check(kind="command", spec=str(c))) for c in raw_checks]
        raw_deps = spec.get("dependencies") or spec.get("depends_on") or spec.get("blocked_by") or []
        executor_role = self.queue_registry.get(queue_id).executor_roles[0]
        ticket = new_ticket(
            tid, title=title, type=ttype, goal=goal,
            created_by=spec.get("created_by", "orchestrator"), audit=self.audit, checks=checks,
            reason=spec.get("reason") or spec.get("why"),
            dependencies=[d for d in raw_deps if d in self.tickets],
            spawned_by=spec.get("spawned_by"), role=executor_role, queue=queue_id,
            difficulty=float(spec.get("difficulty", 0.5)),
        )
        self._register_ticket(ticket)
        self._ticket_index[dedup_key] = tid
        return tid

    def _register_ticket(self, ticket: Ticket) -> None:
        self.tickets[ticket.id] = ticket
        self.graph.add_ticket(ticket, spawned_by=ticket.spawned_by)
        self.queue_registry.get(ticket.queue).add(ticket)

    def _on_summon(self, role: str, requester: str) -> None:
        """A model summoned @role via a comment. If that role/queue does not exist, route the
        request to the birthgiver as an incoming ticket (PHASE_3 Context Exploration)."""
        if self.role_registry.has(role) or self.role_registry.has(f"{role}-exec") or self.queue_registry.has(role):
            return
        summon = self.birthgiver.summon_ticket(role, requester=requester)
        self._register_ticket(summon)

    # -- final verification ---------------------------------------------------
    def _final_verification(self) -> tuple[str, Optional[str]]:
        if self.budget.blocked:
            return "budget_exceeded", "project budget exhausted (soft stop)"
        failed = [t.id for t in self.tickets.values() if t.status == Status.FAILED]
        if not self.scenario.verification_commands and not self.scenario.verification_criteria:
            status = "done" if not failed else "failed"
            return status, (f"failed tickets: {failed}" if failed else None)
        checks = [Check(kind="command", spec=c) for c in self.scenario.verification_commands]
        checks += [Check(kind="model", spec=c) for c in self.scenario.verification_criteria]
        verify = new_ticket("scenario-verify", title="final verification", type="verify",
                            goal=f"Verify scenario goal is met: {self.scenario.goal_text}",
                            created_by="orchestrator", audit=self.audit, checks=checks,
                            role="verification-exec", queue="verification")
        self.tickets[verify.id] = verify
        self.graph.add_ticket(verify)
        verify.transition(Status.READY, actor="orchestrator", audit=self.audit)
        result = self._run_executor_cycle_wrap(verify, "verification")
        if result == Status.DONE and not failed:
            return "done", None
        return "failed", (f"final verification {result}; failed tickets: {failed}" if failed else f"final verification {result}")

    def _run_executor_cycle_wrap(self, ticket: Ticket, queue_id: str) -> str:
        role = self.role_registry.get(self.queue_registry.get(queue_id).executor_roles[0])
        ticket.transition(Status.RUNNING, actor=role.id, audit=self.audit)
        return self._run_cycle(ticket, queue_id, role=role).status

    # -- persistence ----------------------------------------------------------
    def _persist(self, result: RunResult) -> None:
        (self.run_dir / "graph.json").write_text(json.dumps(self.graph.to_dict(), indent=2), encoding="utf-8")
        (self.run_dir / "scores.json").write_text(json.dumps(self.score.to_dict(), indent=2), encoding="utf-8")
        (self.run_dir / "scenario.json").write_text(json.dumps(self.scenario.to_dict(), indent=2), encoding="utf-8")
        (self.run_dir / "tickets.json").write_text(
            json.dumps({tid: t.to_dict() for tid, t in self.tickets.items()}, indent=2), encoding="utf-8")
        (self.run_dir / "result.json").write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        # Final static, server-free Visibility report + the structured Run Analysis.
        self._write_report()
        self._build_analysis()

    def _record_model_io(self, event: Dict[str, Any]) -> None:
        try:
            with self._model_io_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "cycle_id": event.get("cycle_id"), "ticket_id": event.get("ticket_id"),
                    "phase": event.get("phase"), "model": event.get("model"),
                    "thinking": event.get("thinking"), "content": event.get("content"),
                    "tokens": event.get("tokens"),
                }, ensure_ascii=False, default=str) + "\n")
        except OSError:
            pass

    def _snapshot(self) -> Dict[str, Any]:
        vis = self.vis.snapshot()
        ticket_budgets = []
        for tid, b in self.ticket_budgets.items():
            t = self.tickets.get(tid)
            ticket_budgets.append({"ticket": tid, "title": t.title if t else tid,
                                   "goal": t.goal if t else "", "usage": b.snapshot(),
                                   "limits": dict(b.limits), "exceeded": b.exceeded})
        return {
            "scenario": {"name": self.scenario.name, "goal": self.scenario.goal_text,
                         "constraints": list(self.scenario.constraints),
                         "verification_commands": list(self.scenario.verification_commands),
                         "verification_criteria": list(self.scenario.verification_criteria)},
            "status": self._status,
            "cycles_run": self.cycles_run,
            "tickets": {tid: t.to_dict() for tid, t in self.tickets.items()},
            "graph": self.graph.to_dict(),
            "queues": {qid: q.to_dict() for qid, q in self.queue_registry.queues.items()},
            "budgets": {"project": self.budget.to_dict(), "tickets": ticket_budgets},
            "scores": self.score.to_dict(),
            "kb": self.kb.to_dict(),
            "tools": vis.get("tools", {}),
            "commands": vis.get("commands", []),
            "cycles": vis.get("cycles", {}),
            "cycle_tree": vis.get("cycle_tree", []),
            "log": self.vis.recent_log(4000),
        }

    def _write_report(self) -> None:
        try:
            from planfoldr.visibility.web import write_report
            write_report(self.run_dir, self._snapshot())
        except Exception:  # noqa: BLE001 -- reporting must never break the run
            pass

    def _build_analysis(self) -> None:
        from planfoldr.visibility.analysis import build_analysis
        snapshot = self._snapshot()
        md, html = build_analysis(snapshot)
        (self.run_dir / "analysis.md").write_text(md, encoding="utf-8")
        (self.run_dir / "visibility" / "analysis.html").write_text(html, encoding="utf-8")


def _ollama_ps() -> str:
    try:
        return subprocess.run(["ollama", "ps"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def run_scenario(scenario: Scenario, **kwargs: Any) -> RunResult:
    return Orchestrator(scenario, **kwargs).run()
