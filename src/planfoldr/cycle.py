"""Cycle (level 5b) -- the base unit of work over a ticket.

Runs four phases in strict order: Context Exploration → Changes → Command Verification → Model
Verification. Not every ticket type needs all four (research = context + model verify; verify =
command + model verify), but the order never breaks. The Changes phase is a bounded JSON-action
loop where the model drives the allowed tools. Each phase emits a `cycle.phase_completed` event.

PHASE_3 "Базовый цикл" + PHASE_4 §2. Properties: execution_id, ticket_id, role, model, phase,
local_memory (ephemeral, never leaks), budget_used, parent_cycle_id, spawned_tickets. Constraints
flow down (via the ticket), facts flow up (via `output`). The parent owns the tree; a child cycle
updates its own ticket but cannot declare the whole project done. Budget is delegated and cannot
be exceeded without an approved request_decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from planfoldr.audit import AuditLog, EventType
from planfoldr.budget import Budget, Metric
from planfoldr.model import Action, ModelAdapter, ModelConfig, parse_action
from planfoldr.score import ScoreSystem
from planfoldr.ticket import Status, Ticket
from planfoldr.tools_impl import ToolContext, run_command
from planfoldr.toolset import ToolDenied, Toolset
from planfoldr.util import new_id

CONTEXT = "context_exploration"
CHANGES = "changes"
COMMAND_VERIFY = "command_verification"
MODEL_VERIFY = "model_verification"

PHASES_BY_TYPE: Dict[str, List[str]] = {
    "research": [CONTEXT, MODEL_VERIFY],
    "verify": [COMMAND_VERIFY, MODEL_VERIFY],
    "documentation": [CONTEXT, CHANGES, MODEL_VERIFY],
    # The top/orchestration cycle plans and decomposes; it does not verify code itself.
    "orchestration": [CONTEXT, CHANGES],
    "plan": [CONTEXT, CHANGES],
    "decompose": [CONTEXT, CHANGES],
}
DEFAULT_PHASES = [CONTEXT, CHANGES, COMMAND_VERIFY, MODEL_VERIFY]

_PROTOCOL = (
    "Respond with ONE JSON object and nothing else: "
    '{"thinking": "<one short sentence>", "action": "<name>", "args": {...}}. '
    "Keep 'thinking' to a single brief sentence. Never wrap it in markdown."
)

_ACTION_REFERENCE = {
    "file_edit": '{"action":"file_edit","args":{"path":"relative/file.py","content":"<FULL file content>"}} — creates/overwrites a file in the workspace',
    "bash": '{"action":"bash","args":{"cmd":"<shell command>"}} — run a command in the workspace (use rarely; do not repeat read-only commands)',
    "create_ticket": '{"action":"create_ticket","args":{"type":"code|tests|research|fix|verify","title":"...","goal":"<concrete goal>","dependencies":["<ticket-id>"],"checks":[{"kind":"command","spec":"<shell test that exits 0 on success>"}]}}',
    "update_ticket": '{"action":"update_ticket","args":{"finding":"<evidence/notes>","status":"note"}}',
    "comment": '{"action":"comment","args":{"text":"<comment>","summon":"<@role to call, optional>"}}',
    "write_context": '{"action":"write_context","args":{"section":"<name>","content":"..."}}',
    "read_context": '{"action":"read_context","args":{"section":"<name>"}}',
    "request_decision": '{"action":"request_decision","args":{"question":"<ask @human>"}}',
    "request_context": '{"action":"request_context","args":{"question":"<ask parent>"}}',
    "verify": '{"action":"verify","args":{"passed":true,"reason":"<why the evidence proves the goal>"}}',
    "plan": '{"action":"plan","args":{"notes":"<short plan>"}}',
    "finish": '{"action":"finish","args":{}} — use when the GOAL is achieved',
}


@dataclass
class CycleResult:
    execution_id: str
    ticket_id: str
    status: str                       # done | failed | needs_review | budget_exceeded
    phases: List[str] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    spawned_tickets: List[str] = field(default_factory=list)
    budget_used: Dict[str, float] = field(default_factory=dict)
    output: Dict[str, Any] = field(default_factory=dict)
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id, "ticket_id": self.ticket_id, "status": self.status,
            "phases": self.phases, "evidence": self.evidence, "spawned_tickets": self.spawned_tickets,
            "budget_used": self.budget_used, "output": self.output, "reason": self.reason,
        }


class Cycle:
    def __init__(
        self,
        *,
        ticket: Ticket,
        role: Any,
        model_config: ModelConfig,
        model_adapter: ModelAdapter,
        budget: Budget,
        audit: AuditLog,
        toolset: Toolset,
        workspace: Path,
        graph: Any = None,
        knowledge_base: Any = None,
        score_system: Optional[ScoreSystem] = None,
        parent_cycle_id: Optional[str] = None,
        allowed_paths: Optional[List[Path]] = None,
        on_create_ticket: Optional[Callable[[Dict[str, Any]], str]] = None,
        on_request_decision: Optional[Callable[[str, str], str]] = None,
        on_summon: Optional[Callable[[str, str], None]] = None,
        stream_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
        ps_provider: Optional[Callable[[], str]] = None,
        report_hook: Optional[Callable[[], None]] = None,
        scenario_contract: Optional[Dict[str, Any]] = None,
        max_iterations: int = 8,
        spawn_cap: int = 6,
    ) -> None:
        self.ticket = ticket
        self.role = role
        self.model_config = model_config
        self.model = model_adapter
        self.budget = budget
        self.audit = audit
        self.toolset = toolset
        self.workspace = workspace
        self.graph = graph
        self.knowledge_base = knowledge_base
        self.score_system = score_system
        self.parent_cycle_id = parent_cycle_id
        self.stream_sink = stream_sink
        self.ps_provider = ps_provider
        self.report_hook = report_hook
        self.scenario_contract = scenario_contract or {}
        self.max_iterations = max_iterations
        self.spawn_cap = spawn_cap
        self.execution_id = new_id("exec")
        self.local_memory: Dict[str, Any] = {"changes_log": [], "context": {}}
        self.spawned_tickets: List[str] = []
        self.phase: Optional[str] = None
        self._budget_exceeded = False
        self._tool_ctx = ToolContext(
            audit=audit, budget=budget, workspace=workspace, ticket=ticket, role=role, graph=graph,
            knowledge_base=knowledge_base, allowed_paths=allowed_paths or [workspace],
            on_create_ticket=self._wrap_create_ticket(on_create_ticket),
            on_request_decision=on_request_decision, on_summon=on_summon,
        )

    # -- public ---------------------------------------------------------------
    def run(self) -> CycleResult:
        self.audit.emit(
            EventType.CYCLE_STARTED, ticket_id=self.ticket.id, cycle_id=self.execution_id,
            role=getattr(self.role, "id", None), model=self.model_config.id,
            parent_cycle_id=self.parent_cycle_id, type=self.ticket.type,
        )
        self.ticket.record_attempt()
        phases = PHASES_BY_TYPE.get(self.ticket.type, DEFAULT_PHASES)
        ran: List[str] = []
        for phase in phases:
            self.phase = phase
            getattr(self, f"_phase_{phase}")()
            ran.append(phase)
            self.audit.emit(
                EventType.CYCLE_PHASE_COMPLETED, ticket_id=self.ticket.id, cycle_id=self.execution_id,
                phase=phase, budget=self.budget.snapshot(),
            )
            if self.report_hook is not None:
                try:
                    self.report_hook()  # refresh the live HTML report after each phase
                except Exception:  # noqa: BLE001 -- reporting must never break the run
                    pass
            if self.budget.blocked:
                self._budget_exceeded = True
                break
        return self._finalize(ran)

    # -- phases ---------------------------------------------------------------
    def _phase_context_exploration(self) -> None:
        context = {
            "goal": self.ticket.goal,
            "checks": [c.to_dict() for c in self.ticket.checks],
            "prior_evidence": list(self.ticket.evidence),
            "dependencies": list(self.ticket.dependencies),
        }
        if self.graph is not None:
            from planfoldr.graph import EVIDENCE_FOR, RELATED_TO
            context["related"] = self.graph.related(self.ticket.id, RELATED_TO)
            context["evidence_for"] = self.graph.related(self.ticket.id, EVIDENCE_FOR)
        self.local_memory["context"] = context
        # Context Exploration is where tickets are managed: plan, read/write KB, create tickets,
        # update findings, comment / summon roles (PHASE_3 "Context exploration").
        self._action_loop(
            CONTEXT,
            allowed={"plan", "read_context", "write_context", "create_ticket", "update_ticket",
                     "comment", "request_decision", "request_context", "finish"},
            max_iterations=1,  # context is a single lightweight planning pass; work happens in changes
        )

    def _phase_changes(self) -> None:
        # Changes works the working copy: domain tools + new tickets + KB writes. It does NOT
        # modify existing tickets or leave comments (PHASE_3 "Изменения в рабочей копии").
        self._action_loop(
            CHANGES,
            allowed={"file_edit", "bash", "create_ticket", "write_context",
                     "read_context", "request_decision", "finish"},
            max_iterations=self.max_iterations,
        )

    def _phase_command_verification(self) -> None:
        for idx, check in enumerate(self.ticket.checks):
            if check.kind != "command":
                continue
            result = run_command(check.spec, cwd=self.workspace, timeout=self._tool_ctx.command_timeout, budget=self.budget)
            proof = f"$ {check.spec}\nexit={result['exit_code']}"
            if result.get("stdout"):
                proof += f"\nstdout: {result['stdout'][:300]}"
            if result.get("stderr"):
                proof += f"\nstderr: {result['stderr'][:300]}"
            self.ticket.add_evidence(check_index=idx, status=result["status"], proof=proof)
            # Record the command as a traceable event (who/when/cmd/exit) for Visibility.
            self.audit.emit(
                EventType.TOOL_INVOKED, ticket_id=self.ticket.id, cycle_id=self.execution_id,
                actor=getattr(self.role, "id", "verifier"), tool="command_verification",
                scope="command_verification", args={"cmd": check.spec},
                result={"exit_code": result["exit_code"], "status": result["status"]},
            )
            self._emit_tool("command_verification", {"check": check.spec}, result)

    def _phase_model_verification(self) -> None:
        model_checks = [c for c in self.ticket.checks if c.kind == "model"]
        criteria = [c.spec for c in model_checks] or [self.ticket.goal]
        evidence_repr = [e for e in self.ticket.evidence]
        action = self._one_action(
            MODEL_VERIFY,
            user=(
                f"PHASE: model_verification. Judge whether the goal is met by the evidence.\n"
                f"Goal: {self.ticket.goal}\nCriteria: {criteria}\nEvidence: {evidence_repr}\n"
                'Respond {"action":"verify","args":{"passed":true|false,"reason":"..."}}.'
            ),
            allowed={"verify"},
        )
        passed = bool(action.args.get("passed", False)) if action.action == "verify" else False
        reason = action.args.get("reason", "")
        # Detect a false verification: model claims pass while command evidence shows failure.
        cmd_fail = any(e.get("status") == "failure" for e in self.ticket.evidence)
        self.local_memory["verdict"] = {"passed": passed, "reason": reason, "false_verification": passed and cmd_fail}

    # -- action loop ----------------------------------------------------------
    # Actions handled by the cycle itself rather than by a tool in the role's toolset.
    _NON_TOOL_ACTIONS = {"finish", "plan", "verify", "note"}

    def _effective_allowed(self, allowed: set) -> set:
        """Only offer actions the role can actually perform: phase actions ∩ role toolset (plus the
        cycle-handled non-tool actions). Prevents e.g. the orchestrator being offered file_edit."""
        return {a for a in allowed if a in self._NON_TOOL_ACTIONS or self.toolset.can(a)}

    def _action_loop(self, phase: str, *, allowed: set, max_iterations: int) -> None:
        allowed = self._effective_allowed(allowed)
        last_result: Optional[Dict[str, Any]] = None
        reformat_left = 2
        last_sig: Optional[str] = None
        repeats = 0
        no_progress = 0
        seen_tickets: set = set()
        for _ in range(max_iterations):
            if self.budget.blocked:
                return
            action = self._one_action(phase, user=self._changes_user(phase, allowed, last_result), allowed=allowed)
            if action.error and reformat_left > 0:
                reformat_left -= 1
                last_result = {"protocol_error": action.error, "hint": "Reply with exactly one JSON action object."}
                continue
            if action.action in {"finish", ""}:
                return
            # Break out of a model stuck repeating the identical action (e.g. ls -R loops).
            sig = f"{action.action}:{action.args!r}"
            repeats = repeats + 1 if sig == last_sig else 0
            last_sig = sig
            if repeats >= 2:
                self.local_memory.setdefault("notes", []).append(f"stopped repeated action {action.action}")
                return
            if action.action == "plan":
                self.local_memory.setdefault("plan", []).append(action.args.get("notes", action.thinking))
                last_result = {"ok": True}
                continue
            if action.action not in allowed:
                last_result = {"error": f"action '{action.action}' not allowed in {phase}; allowed: {sorted(allowed)}"}
                continue
            try:
                result = self.toolset.invoke(
                    action.action, audit=self.audit, actor=getattr(self.role, "id", "model"),
                    ticket_id=self.ticket.id, cycle_id=self.execution_id, args=action.args, ctx=self._tool_ctx,
                )
            except (ToolDenied, Exception) as exc:  # noqa: BLE001 -- surface tool errors back to the model
                result = {"error": str(exc)}
            self.local_memory["changes_log"].append({"action": action.action, "result": result})
            self._emit_tool(phase, {"action": action.action, "args": action.args}, result)
            last_result = result
            # No-progress detection: a model that keeps erroring, or re-creating an existing ticket
            # (deduped), or rejected, isn't advancing -> stop instead of burning the whole iteration
            # budget. (Decomposition usually needs only 1-2 productive actions.)
            productive = True
            if not isinstance(result, dict) or result.get("error") or result.get("status") == "rejected":
                productive = False
            elif action.action == "create_ticket":
                tid = result.get("ticket_id")
                productive = tid not in seen_tickets
                seen_tickets.add(tid)
            no_progress = 0 if productive else no_progress + 1
            if no_progress >= 2:
                self.local_memory.setdefault("notes", []).append("stopped: no further progress")
                return

    # -- model call -----------------------------------------------------------
    def _one_action(self, phase: str, *, user: str, allowed: set) -> Action:
        system = f"{getattr(self.role, 'effective_prompt', lambda *a: '')(self.ticket.queue) if self.role else ''}\n{_PROTOCOL}\nAllowed actions: {sorted(allowed)}"
        messages = [{"role": "system", "content": system.strip()}, {"role": "user", "content": user}]
        chunks: List[str] = []

        def progress(event: str, fields: Dict[str, Any]) -> None:
            if event == "model_stream_chunk":
                chunks.append(fields.get("text", ""))
            if self.stream_sink is not None:
                self.stream_sink({"phase": phase, "event": event, "cycle_id": self.execution_id,
                                  "ticket_id": self.ticket.id, **fields})

        response = self.model.generate(messages, fmt="json", progress=progress)
        # Emit the FULL assembled output (thinking + content) so the report never loses the start
        # of a stream (the per-token chunks above are for live terminal/WS only).
        if self.stream_sink is not None:
            self.stream_sink({
                "event": "model_output", "cycle_id": self.execution_id, "ticket_id": self.ticket.id,
                "phase": phase, "model": self.model_config.id, "thinking": response.thinking,
                "content": response.content, "tokens": response.total_tokens,
                "input": {"system": system, "user": user},
            })
        # Budget accounting happens in the cycle, not the model.
        self.budget.consume(Metric.API_REQUESTS, 1)
        self.budget.consume(Metric.TOKENS, response.total_tokens)
        if self.model_config.cost_per_token:
            self.budget.consume(Metric.MONEY, response.total_tokens * self.model_config.cost_per_token)
        if self.ps_provider is not None and response.duration_seconds:
            self.budget.charge_model_seconds(self.model_config.id, response.duration_seconds, ps_provider=self.ps_provider)
        self.audit.emit(
            EventType.MODEL_STREAM, ticket_id=self.ticket.id, cycle_id=self.execution_id, phase=phase,
            model=self.model_config.id, content_chars=len(response.content),
            thinking_chars=len(response.thinking), tokens=response.total_tokens,
        )
        return parse_action(response.content)

    def _contract_block(self) -> str:
        """The originating scenario's contract: the project goal plus the exact acceptance commands
        the final gate runs. Decomposition paraphrases each child ticket's goal and can drop the
        interface (the "...as specified" collapse); surfacing the real contract to every executor
        means the implementer always sees the exact API/CLI it will be judged on instead of guessing
        it. Empty for direct Cycle use without a scenario (e.g. unit tests)."""
        c = self.scenario_contract
        if not c:
            return ""
        lines = ["PROJECT CONTRACT — the whole project is judged by this; make your work conform to it:"]
        if c.get("goal"):
            lines.append(f"- Project goal: {c['goal']}")
        if c.get("verification_commands"):
            lines.append("- Acceptance commands that MUST pass (they encode the exact interface — match the "
                         "module / function / CLI names, signatures, path arguments and return values they "
                         "assume; do not invent your own):")
            lines += [f"    $ {cmd}" for cmd in c["verification_commands"]]
        if c.get("verification_criteria"):
            lines.append(f"- Acceptance criteria: {list(c['verification_criteria'])}")
        if c.get("constraints"):
            lines.append(f"- Project constraints: {list(c['constraints'])}")
        return "\n".join(lines) + "\n"

    def _checks_block(self) -> str:
        """Format ticket command-checks as a prominent pre-finish checklist for the developer."""
        cmds = [c.spec for c in self.ticket.checks if c.kind == "command"]
        if not cmds:
            return ""
        lines = ["ACCEPTANCE CHECKS — run ALL of these with bash and confirm they exit 0 before calling finish:"]
        lines += [f"  $ {cmd}" for cmd in cmds]
        return "\n".join(lines) + "\n"

    def _changes_user(self, phase: str, allowed: set, last_result: Optional[Dict[str, Any]]) -> str:
        ref = "\n".join(f"- {_ACTION_REFERENCE[a]}" for a in sorted(allowed) if a in _ACTION_REFERENCE)
        constraints = self.ticket.metadata.get("constraints") or []
        return (
            f"PHASE: {phase}. You are working on ticket {self.ticket.id} ({self.ticket.type}).\n"
            + self._contract_block()
            + f"GOAL: {self.ticket.goal}\n"
            + (f"CONSTRAINTS: {constraints}\n" if constraints else "")
            + self._checks_block()
            + f"CONTEXT: {self.local_memory.get('context', {})}\n"
            "The workspace is the current directory and may be empty; CREATE the files needed to "
            "achieve the GOAL using file_edit (provide the full file content). NEVER write files "
            "with bash (no echo/printf/cat/tee redirects) — use file_edit. Use bash ONLY to run "
            "tests or commands. Do not repeat read-only commands. When ALL acceptance checks pass, "
            "respond with finish.\n"
            f"ACTION REFERENCE (choose exactly ONE):\n{ref}\n"
            f"Last tool result: {last_result}\n"
            f"{_PROTOCOL}"
        )

    # -- finalize -------------------------------------------------------------
    def _finalize(self, ran: List[str]) -> CycleResult:
        verdict = self.local_memory.get("verdict", {})
        ran_cmd = COMMAND_VERIFY in ran
        ran_model = MODEL_VERIFY in ran
        cmd_ok = (not ran_cmd) or all(
            any(e.get("check_index") == i and e.get("status") == "success" for e in self.ticket.evidence)
            for i, c in enumerate(self.ticket.checks) if c.kind == "command" and c.required
        )
        model_ok = (not ran_model) or bool(verdict.get("passed"))
        passed = cmd_ok and model_ok and not self._budget_exceeded

        if self._budget_exceeded:
            status = "budget_exceeded"
            reason = "budget exceeded; soft stop"
        elif passed:
            proof = verdict.get("reason") or "all mandatory checks passed"
            self.ticket.transition(Status.DONE, actor=getattr(self.role, "id", "executor"), audit=self.audit, proof=proof)
            status = Status.DONE
            reason = None
        elif self.ticket.exhausted_attempts():
            self.ticket.transition(Status.FAILED, actor=getattr(self.role, "id", "executor"), audit=self.audit)
            status = Status.FAILED
            reason = "verification failed; attempts exhausted"
        else:
            self.ticket.transition(Status.NEEDS_REVIEW, actor=getattr(self.role, "id", "executor"), audit=self.audit)
            status = Status.NEEDS_REVIEW
            reason = "verification not passed"

        if self.score_system is not None:
            self.score_system.record(
                self.model_config.id, role=getattr(self.role, "id", "executor"), task_type=self.ticket.type,
                passed=(status == Status.DONE), verified=(status == Status.DONE and ran_model),
                difficulty=self.ticket.difficulty,
                tokens_used=self.budget.usage.get(Metric.TOKENS, 0),
                tokens_budget=self.budget.limits.get(Metric.TOKENS, 0),
                budget_exhausted=self._budget_exceeded,
                false_verification=bool(verdict.get("false_verification")),
            )

        self.audit.emit(
            EventType.CYCLE_COMPLETED, ticket_id=self.ticket.id, cycle_id=self.execution_id,
            status=status, spawned=self.spawned_tickets, budget=self.budget.snapshot(),
        )
        # Facts flow up via output; local_memory is discarded (ephemeral, never leaks).
        return CycleResult(
            execution_id=self.execution_id, ticket_id=self.ticket.id, status=status, phases=ran,
            evidence=list(self.ticket.evidence), spawned_tickets=list(self.spawned_tickets),
            budget_used=self.budget.snapshot(),
            output={"summary": reason or "completed", "verdict": verdict, "spawned": self.spawned_tickets},
            reason=reason,
        )

    # -- helpers --------------------------------------------------------------
    def _wrap_create_ticket(self, fn: Optional[Callable[[Dict[str, Any]], str]]):
        if fn is None:
            return None

        def wrapped(spec: Dict[str, Any]) -> str:
            distinct = len(set(self.spawned_tickets))
            if distinct >= self.spawn_cap:
                from planfoldr.tools_impl import ToolError
                raise ToolError(f"ticket limit ({self.spawn_cap}) reached for this cycle; respond with finish")
            spec.setdefault("spawned_by", self.ticket.id)
            ticket_id = fn(spec)
            self.spawned_tickets.append(ticket_id)
            return ticket_id

        return wrapped

    def _emit_tool(self, phase: str, call: Dict[str, Any], result: Dict[str, Any]) -> None:
        if self.stream_sink is not None:
            self.stream_sink({"phase": phase, "event": "tool_result", "call": call, "result": result})
