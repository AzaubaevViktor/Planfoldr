"""End-to-end orchestration with a deterministic StubModel (hermetic, offline).

Exercises PHASE_3 flow Steps 1-9: scenario → top cycle → dynamic tickets → graph dependency
resolution → executor cycles → final verification, plus budget soft-stop and a failed-scenario
path. This is the Quest-6 readiness checklist as an automated test.
"""

import json
import re
from pathlib import Path

from planfoldr.budget import Metric
from planfoldr.model import StubModel
from planfoldr.orchestrator import run_scenario
from planfoldr.scenario import ModelSettings, Scenario


def make_e2e_stub():
    state = {"top_step": 0, "wrote": set()}

    def stub(messages):
        text = messages[-1]["content"]
        if "PHASE: context_exploration" in text:
            return {"action": "finish", "args": {}}
        if "PHASE: model_verification" in text:
            return {"action": "verify", "args": {"passed": True, "reason": "evidence supports the goal"}}
        if "PHASE: changes" in text:
            if "(orchestration)" in text:
                steps = [
                    {"action": "create_ticket", "args": {"id": "developer-1", "type": "code", "title": "impl alpha",
                        "goal": "create file alpha.txt", "checks": [{"kind": "command", "spec": "test -f alpha.txt"}]}},
                    {"action": "create_ticket", "args": {"id": "developer-2", "type": "tests", "title": "impl beta",
                        "goal": "create file beta.txt", "dependencies": ["developer-1"],
                        "checks": [{"kind": "command", "spec": "test -f beta.txt"}]}},
                    {"action": "finish", "args": {}},
                ]
                i = state["top_step"]
                state["top_step"] = i + 1
                return steps[min(i, len(steps) - 1)]
            m = re.search(r"create file (\S+)", text)
            if m and m.group(1) not in state["wrote"]:
                state["wrote"].add(m.group(1))
                return {"action": "file_edit", "args": {"path": m.group(1), "content": "ok\n"}}
            return {"action": "finish", "args": {}}
        return {"action": "finish", "args": {}}

    return stub


def base_scenario(**over):
    return Scenario(
        name="e2e", goal_text="build alpha and beta files",
        budget=over.get("budget", {Metric.TOKENS: 1_000_000}),
        verification_commands=over.get("commands", ["test -f alpha.txt", "test -f beta.txt"]),
        verification_criteria=["both files present"],
        model=ModelSettings(provider="stub", name="stub", parameter_count=1e9),
    )


def test_full_scenario_completes_and_persists(tmp_path):
    result = run_scenario(base_scenario(), runs_dir=tmp_path, run_id="test_run_e2e",
                          model_adapter=StubModel(make_e2e_stub()))
    assert result.status == "done", result.reason
    # Tickets were created dynamically via create_ticket and both completed.
    assert result.tickets["developer-1"] == "done" and result.tickets["developer-2"] == "done"
    ws = Path(result.run_dir) / "workspace"
    assert (ws / "alpha.txt").exists() and (ws / "beta.txt").exists()
    # Artifacts persisted for replay/inspection.
    for name in ["audit.jsonl", "graph.json", "scores.json", "tickets.json", "result.json"]:
        assert (Path(result.run_dir) / name).exists()
    # Budget was metered in real time.
    assert result.budget[Metric.TOKENS] > 0


def test_dependency_resolved_via_graph(tmp_path):
    result = run_scenario(base_scenario(), runs_dir=tmp_path, run_id="test_run_deps",
                          model_adapter=StubModel(make_e2e_stub()))
    graph = json.loads((Path(result.run_dir) / "graph.json").read_text())
    assert any(l["type"] == "blocked_by" and l["src"] == "developer-2" and l["dst"] == "developer-1"
               for l in graph["links"])
    # developer-2 only became ready (and ran) after developer-1 was done.
    audit = [json.loads(x) for x in (Path(result.run_dir) / "audit.jsonl").read_text().splitlines()]
    dev1_done = next(e["seq"] for e in audit if e["ticket_id"] == "developer-1"
                     and e["event_type"] == "ticket.status_changed" and e["payload"]["to"] == "done")
    dev2_running = next(e["seq"] for e in audit if e["ticket_id"] == "developer-2"
                        and e["event_type"] == "ticket.status_changed" and e["payload"]["to"] == "running")
    assert dev1_done < dev2_running


def test_audit_has_every_phase_and_tool_call(tmp_path):
    result = run_scenario(base_scenario(), runs_dir=tmp_path, run_id="test_run_audit",
                          model_adapter=StubModel(make_e2e_stub()))
    audit = [json.loads(x) for x in (Path(result.run_dir) / "audit.jsonl").read_text().splitlines()]
    types = {e["event_type"] for e in audit}
    assert {"scenario.started", "ticket.created", "cycle.phase_completed", "tool.invoked",
            "cycle.completed", "model.score_updated", "scenario.completed"} <= types
    phases = {e["payload"]["phase"] for e in audit if e["event_type"] == "cycle.phase_completed"}
    assert {"context_exploration", "changes", "command_verification", "model_verification"} <= phases


def test_budget_soft_stop_stops_the_run(tmp_path):
    result = run_scenario(base_scenario(budget={Metric.TOKENS: 30}), runs_dir=tmp_path,
                          run_id="test_run_budget", model_adapter=StubModel(make_e2e_stub()))
    assert result.status == "budget_exceeded"
    audit_types = {json.loads(x)["event_type"] for x in (Path(result.run_dir) / "audit.jsonl").read_text().splitlines()}
    assert "budget.exceeded" in audit_types


def test_orchestrator_dedupes_duplicate_tickets(tmp_path):
    """The orchestration cycle re-creating the same work yields ONE ticket, not duplicates."""
    def stub_factory():
        state = {"top": 0, "wrote": set()}

        def stub(messages):
            text = messages[-1]["content"]
            if "PHASE: context_exploration" in text:
                return {"action": "finish", "args": {}}
            if "PHASE: model_verification" in text:
                return {"action": "verify", "args": {"passed": True, "reason": "ok"}}
            if "PHASE: changes" in text:
                if "(orchestration)" in text:
                    steps = [
                        {"action": "create_ticket", "args": {"type": "code", "title": "impl",
                            "goal": "create file alpha.txt", "checks": [{"kind": "command", "spec": "test -f alpha.txt"}]}},
                        # Duplicate of the same work (different title + casing) -> must dedupe.
                        {"action": "create_ticket", "args": {"type": "code", "title": "impl again",
                            "goal": "Create file alpha.txt", "checks": [{"kind": "command", "spec": "test -f alpha.txt"}]}},
                        {"action": "finish", "args": {}},
                    ]
                    i = state["top"]
                    state["top"] = i + 1
                    return steps[min(i, len(steps) - 1)]
                m = re.search(r"create file (\S+)", text)
                if m and m.group(1) not in state["wrote"]:
                    state["wrote"].add(m.group(1))
                    return {"action": "file_edit", "args": {"path": m.group(1), "content": "ok\n"}}
                return {"action": "finish", "args": {}}
            return {"action": "finish", "args": {}}
        return stub

    result = run_scenario(base_scenario(commands=["test -f alpha.txt"]), runs_dir=tmp_path,
                          run_id="test_run_dedup", model_adapter=StubModel(stub_factory()))
    dev = [t for t in result.tickets if t.startswith("developer-")]
    assert len(dev) == 1, result.tickets  # deduped
    assert result.status == "done"


def test_scenario_done_when_gate_passes_despite_failed_spawned_ticket(tmp_path):
    """Scenario success is the human verification gate, not whether every spawned ticket succeeded."""
    def stub_factory():
        state = {"top": 0, "wrote": set()}

        def stub(messages):
            text = messages[-1]["content"]
            if "PHASE: context_exploration" in text:
                return {"action": "finish", "args": {}}
            if "PHASE: model_verification" in text:
                return {"action": "verify", "args": {"passed": True, "reason": "ok"}}
            if "PHASE: changes" in text:
                if "(orchestration)" in text:
                    steps = [
                        {"action": "create_ticket", "args": {"type": "code", "title": "impl",
                            "goal": "create file alpha.txt", "checks": [{"kind": "command", "spec": "test -f alpha.txt"}]}},
                        # A tests ticket with a check that always fails (model's buggy self-check).
                        {"action": "create_ticket", "args": {"type": "tests", "title": "buggy tests",
                            "goal": "add a test suite", "checks": [{"kind": "command", "spec": "false"}]}},
                        {"action": "finish", "args": {}},
                    ]
                    i = state["top"]
                    state["top"] = i + 1
                    return steps[min(i, len(steps) - 1)]
                m = re.search(r"create file (\S+)", text)
                if m and m.group(1) not in state["wrote"]:
                    state["wrote"].add(m.group(1))
                    return {"action": "file_edit", "args": {"path": m.group(1), "content": "ok\n"}}
                return {"action": "finish", "args": {}}
            return {"action": "finish", "args": {}}
        return stub

    result = run_scenario(base_scenario(commands=["test -f alpha.txt"]), runs_dir=tmp_path,
                          run_id="test_run_gate", model_adapter=StubModel(stub_factory()))
    assert result.tickets["developer-2"] == "failed"   # the buggy-check ticket failed
    assert result.status == "done"                     # but the scenario verification gate passed
    assert "spawned ticket" in (result.reason or "")


def test_birthgiver_creates_role_live_for_unknown_type(tmp_path):
    """An unknown ticket type is summoned to birthgiver, which creates the role+queue during the run."""
    def stub_factory():
        state = {"top": 0, "wrote": set()}

        def stub(messages):
            text = messages[-1]["content"]
            if "PHASE: context_exploration" in text:
                return {"action": "finish", "args": {}}
            if "PHASE: model_verification" in text:
                return {"action": "verify", "args": {"passed": True, "reason": "ok"}}
            if "PHASE: changes" in text:
                if "(orchestration)" in text:
                    steps = [
                        {"action": "create_ticket", "args": {"type": "performance", "title": "tune",
                            "goal": "create file gamma.txt", "checks": [{"kind": "command", "spec": "test -f gamma.txt"}]}},
                        {"action": "finish", "args": {}},
                    ]
                    i = state["top"]
                    state["top"] = i + 1
                    return steps[min(i, len(steps) - 1)]
                m = re.search(r"create file (\S+)", text)
                if m and m.group(1) not in state["wrote"]:
                    state["wrote"].add(m.group(1))
                    return {"action": "file_edit", "args": {"path": m.group(1), "content": "ok\n"}}
                return {"action": "finish", "args": {}}
            return {"action": "finish", "args": {}}
        return stub

    result = run_scenario(base_scenario(commands=["test -f gamma.txt"]), runs_dir=tmp_path,
                          run_id="test_run_birth", model_adapter=StubModel(stub_factory()))
    audit = [json.loads(x) for x in (Path(result.run_dir) / "audit.jsonl").read_text().splitlines()]
    # Birthgiver was summoned and created the new role + queue live.
    assert any(e["event_type"] == "role.summoned" and e["payload"].get("role") == "performance" for e in audit)
    assert any(e["event_type"] == "role.created" and e["payload"].get("role") == "performance-exec"
               and e["payload"].get("decision") == "created" for e in audit)
    assert any(e["event_type"] == "queue.created" and e["payload"].get("queue") == "performance" for e in audit)
    assert result.status == "done"  # the work ticket still completed


def test_precheck_short_circuits_already_satisfied_ticket(tmp_path):
    """A ticket whose required command checks already pass is marked done without a model cycle."""
    def stub_factory():
        state = {"top": 0, "wrote": set()}

        def stub(messages):
            text = messages[-1]["content"]
            if "PHASE: context_exploration" in text:
                return {"action": "finish", "args": {}}
            if "PHASE: model_verification" in text:
                return {"action": "verify", "args": {"passed": True, "reason": "ok"}}
            if "PHASE: changes" in text:
                if "(orchestration)" in text:
                    steps = [
                        {"action": "create_ticket", "args": {"type": "code", "title": "impl",
                            "goal": "create file shared.txt", "checks": [{"kind": "command", "spec": "test -f shared.txt"}]}},
                        {"action": "create_ticket", "args": {"type": "tests", "title": "confirm",
                            "goal": "confirm shared file present", "dependencies": ["developer-1"],
                            "checks": [{"kind": "command", "spec": "test -f shared.txt"}]}},
                        {"action": "finish", "args": {}},
                    ]
                    i = state["top"]
                    state["top"] = i + 1
                    return steps[min(i, len(steps) - 1)]
                m = re.search(r"create file (\S+)", text)
                if m and m.group(1) not in state["wrote"]:
                    state["wrote"].add(m.group(1))
                    return {"action": "file_edit", "args": {"path": m.group(1), "content": "ok\n"}}
                return {"action": "finish", "args": {}}
            return {"action": "finish", "args": {}}
        return stub

    result = run_scenario(base_scenario(commands=["test -f shared.txt"]), runs_dir=tmp_path,
                          run_id="test_run_precheck", model_adapter=StubModel(stub_factory()))
    assert result.status == "done"
    audit = [json.loads(x) for x in (Path(result.run_dir) / "audit.jsonl").read_text().splitlines()]
    starts = {e["ticket_id"] for e in audit if e["event_type"] == "cycle.started"}
    assert "developer-1" in starts          # ran a real model cycle
    assert "developer-2" not in starts      # short-circuited (checks already satisfied) -- no model cycle
    assert result.tickets["developer-2"] == "done"


def test_failed_ticket_makes_scenario_fail(tmp_path):
    def failing():
        state = {"top_step": 0}

        def stub(messages):
            text = messages[-1]["content"]
            if "PHASE: context_exploration" in text:
                return {"action": "finish", "args": {}}
            if "PHASE: model_verification" in text:
                return {"action": "verify", "args": {"passed": True, "reason": "i believe it works"}}
            if "PHASE: changes" in text:
                if "(orchestration)" in text:
                    steps = [
                        {"action": "create_ticket", "args": {"id": "developer-1", "type": "code", "title": "impl",
                            "goal": "create file alpha.txt", "difficulty": 0.2,
                            "checks": [{"kind": "command", "spec": "test -f alpha.txt"}]}},
                        {"action": "finish", "args": {}},
                    ]
                    i = state["top_step"]
                    state["top_step"] = i + 1
                    return steps[min(i, len(steps) - 1)]
                return {"action": "finish", "args": {}}  # never writes the file → command check fails
            return {"action": "finish", "args": {}}
        return stub

    result = run_scenario(base_scenario(commands=["test -f alpha.txt"]), runs_dir=tmp_path,
                          run_id="test_run_failed", model_adapter=StubModel(failing()))
    assert result.status == "failed"
    assert result.tickets["developer-1"] == "failed"
    # Score is updated (verification problems are not penalised but the failure still records).
    audit = [json.loads(x) for x in (Path(result.run_dir) / "audit.jsonl").read_text().splitlines()]
    assert any(e["event_type"] == "model.score_updated" for e in audit)
