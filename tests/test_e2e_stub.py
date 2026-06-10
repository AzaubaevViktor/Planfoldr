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
from planfoldr.scenario import ModelSettings, Scenario, load_scenario


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


def multi_model_scenario(**over):
    return Scenario(
        name="e2e_multi_model", goal_text="build alpha file through research",
        budget=over.get("budget", {Metric.TOKENS: 1_000_000}),
        verification_commands=over.get("commands", ["test -f alpha.txt"]),
        verification_criteria=[],
        model=ModelSettings(provider="stub", name="orchestrator-20b", parameter_count=20e9),
        extra_models=[
            ModelSettings(provider="stub", name="worker-14b", parameter_count=14e9),
            ModelSettings(provider="stub", name="worker-9b", parameter_count=9e9),
        ],
    )


def final_command_evidence(result, command):
    tickets = json.loads((Path(result.run_dir) / "tickets.json").read_text())
    verify = tickets.get("scenario-verify", {})
    matches = [e for e in verify.get("evidence", []) if f"$ {command}" in e.get("proof", "")]
    assert matches, (
        f"missing scenario final-verification command evidence\n"
        f"run_dir: {result.run_dir}\ncommand: {command}\n"
        f"available evidence: {verify.get('evidence', [])}"
    )
    return matches[-1]


def assert_final_command_success(result, command, *, stdout_contains=None, example=None):
    evidence = final_command_evidence(result, command)
    proof = evidence.get("proof", "")
    label = f"{example}\n" if example else ""
    assert evidence.get("status") == "success", (
        f"{label}final verification command failed\n"
        f"run_dir: {result.run_dir}\ncommand: {command}\n{proof}"
    )
    assert "exit=0" in proof, (
        f"{label}final verification command did not record exit=0\n"
        f"run_dir: {result.run_dir}\ncommand: {command}\n{proof}"
    )
    if stdout_contains is not None:
        assert stdout_contains in proof, (
            f"{label}final verification command stdout missing marker {stdout_contains!r}\n"
            f"run_dir: {result.run_dir}\ncommand: {command}\n{proof}"
        )


def test_full_scenario_completes_and_persists(tmp_path):
    result = run_scenario(base_scenario(), runs_dir=tmp_path, run_id="test_run_e2e",
                          model_adapter=StubModel(make_e2e_stub()))
    assert result.status == "done", result.reason
    assert_final_command_success(result, "test -f alpha.txt")
    assert_final_command_success(result, "test -f beta.txt")
    # Tickets were created dynamically via create_ticket and both completed.
    assert result.tickets["developer-1"] == "done" and result.tickets["developer-2"] == "done"
    ws = Path(result.run_dir) / "workspace"
    # Secondary artifact inspection; command evidence above is the acceptance proof.
    assert (ws / "alpha.txt").exists() and (ws / "beta.txt").exists()
    # Artifacts persisted for replay/inspection.
    for name in ["audit.jsonl", "graph.json", "scores.json", "tickets.json", "result.json"]:
        assert (Path(result.run_dir) / name).exists()
    # Budget was metered in real time.
    assert result.budget[Metric.TOKENS] > 0


def test_research_ticket_creates_code_ticket_and_run_continues(tmp_path):
    state = {"top": 0, "research_changes": 0, "wrote": False}

    def stub(messages):
        text = messages[-1]["content"]
        if "PHASE: context_exploration" in text:
            return {"action": "finish", "args": {}}
        if "PHASE: model_verification" in text:
            return {"action": "verify", "args": {"passed": True, "reason": "evidence supports the goal"}}
        if "PHASE: changes" in text:
            if "(orchestration)" in text:
                steps = [
                    {"action": "create_ticket", "args": {"id": "research-1", "type": "research",
                        "title": "research alpha", "goal": "Research alpha.txt and create a code ticket."}},
                    {"action": "finish", "args": {}},
                ]
                i = state["top"]
                state["top"] = i + 1
                return steps[min(i, len(steps) - 1)]
            if "(research)" in text:
                state["research_changes"] += 1
                if state["research_changes"] == 1:
                    return {"action": "write_context", "args": {"section": "alpha",
                        "content": "alpha.txt result image, spec, implementation approach, anti-patterns, test plan"}}
                if state["research_changes"] == 2:
                    return {"action": "create_ticket", "args": {"id": "developer-1", "type": "code",
                        "title": "implement alpha", "goal": "create file alpha.txt",
                        "checks": [{"kind": "command", "spec": "test -f alpha.txt"}]}}
                return {"action": "finish", "args": {}}
            if "(code)" in text and not state["wrote"]:
                state["wrote"] = True
                return {"action": "file_edit", "args": {"path": "alpha.txt", "content": "ok\n"}}
            return {"action": "finish", "args": {}}
        return {"action": "finish", "args": {}}

    result = run_scenario(base_scenario(commands=["test -f alpha.txt"]), runs_dir=tmp_path,
                          run_id="test_run_research_to_code", model_adapter=StubModel(stub))

    assert result.status == "done", result.reason
    assert result.tickets["research-1"] == "done"
    assert result.tickets["developer-1"] == "done"
    audit = [json.loads(x) for x in (Path(result.run_dir) / "audit.jsonl").read_text().splitlines()]
    starts = [e["ticket_id"] for e in audit if e["event_type"] == "cycle.started"]
    assert "research-1" in starts
    assert "developer-1" in starts
    tickets = json.loads((Path(result.run_dir) / "tickets.json").read_text())
    assert any("created code ticket developer-1" in e.get("proof", "")
               for e in tickets["research-1"]["evidence"])
    assert_final_command_success(result, "test -f alpha.txt")


def test_rotate_worker_models_uses_extra_models_for_research_and_code(tmp_path):
    state = {"top": 0, "research": 0, "wrote": False}

    def stub(messages):
        text = messages[-1]["content"]
        if "PHASE: context_exploration" in text:
            return {"action": "finish", "args": {}}
        if "PHASE: model_verification" in text:
            return {"action": "verify", "args": {"passed": True, "reason": "ok"}}
        if "PHASE: changes" in text:
            if "(orchestration)" in text:
                steps = [
                    {"action": "create_ticket", "args": {"id": "research-1", "type": "research",
                        "title": "research alpha", "goal": "research alpha and create implementation work"}},
                    {"action": "finish", "args": {}},
                ]
                i = state["top"]
                state["top"] = i + 1
                return steps[min(i, len(steps) - 1)]
            if "(research)" in text:
                state["research"] += 1
                if state["research"] == 1:
                    return {"action": "create_ticket", "args": {"id": "developer-1", "type": "code",
                        "title": "implement alpha", "goal": "create file alpha.txt",
                        "checks": [{"kind": "command", "spec": "test -f alpha.txt"}]}}
                return {"action": "finish", "args": {}}
            if "(code)" in text and not state["wrote"]:
                state["wrote"] = True
                return {"action": "file_edit", "args": {"path": "alpha.txt", "content": "ok\n"}}
            return {"action": "finish", "args": {}}
        return {"action": "finish", "args": {}}

    result = run_scenario(
        multi_model_scenario(), runs_dir=tmp_path, run_id="test_run_rotate_workers",
        model_adapter=StubModel(stub), rotate_worker_models=True,
    )

    assert result.status == "done", result.reason
    audit = [json.loads(x) for x in (Path(result.run_dir) / "audit.jsonl").read_text().splitlines()]
    cycle_models = {
        (e["ticket_id"], e["payload"]["role"]): e["payload"]["model"]
        for e in audit
        if e["event_type"] == "cycle.started"
    }
    assert cycle_models[("orchestration-0", "orchestrator")] == "orchestrator-20b"
    assert cycle_models[("research-1", "research-exec")] == "worker-14b"
    assert cycle_models[("developer-1", "developer-exec")] == "worker-9b"


CALC_EXAMPLE_CONTENT = """\
def add(a, b):
    return a + b


def subtract(a, b):
    return a - b
"""


TODO_EXAMPLE_CONTENT = """\
import json
import sys
from pathlib import Path


def list_tasks(path="todos.json"):
    p = Path(path)
    if not p.exists():
        return []
    return json.loads(p.read_text())


def _save(tasks, path):
    Path(path).write_text(json.dumps(tasks))


def add(title, path="todos.json"):
    tasks = list_tasks(path)
    next_id = max([task["id"] for task in tasks], default=0) + 1
    tasks.append({"id": next_id, "title": title, "done": False})
    _save(tasks, path)
    return next_id


def complete(task_id, path="todos.json"):
    tasks = list_tasks(path)
    found = False
    for task in tasks:
        if task["id"] == int(task_id):
            task["done"] = True
            found = True
    _save(tasks, path)
    return found


def remove(task_id, path="todos.json"):
    tasks = list_tasks(path)
    kept = [task for task in tasks if task["id"] != int(task_id)]
    _save(kept, path)
    return len(kept) != len(tasks)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[0] == "add":
        print(add(argv[1]))
    elif argv[0] == "list":
        for task in list_tasks():
            done = "x" if task["done"] else " "
            print(f"{task['id']} [{done}] {task['title']}")
    elif argv[0] == "done":
        complete(int(argv[1]))
    elif argv[0] == "rm":
        remove(int(argv[1]))
    else:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
"""


def example_file_stub(filename, content):
    state = {"top_step": 0, "wrote": False}

    def stub(messages):
        text = messages[-1]["content"]
        if "PHASE: context_exploration" in text:
            return {"action": "finish", "args": {}}
        if "PHASE: model_verification" in text:
            return {"action": "verify", "args": {"passed": True, "reason": "command evidence passed"}}
        if "PHASE: changes" in text:
            if "(orchestration)" in text:
                steps = [
                    {"action": "create_ticket", "args": {"id": "developer-1", "type": "code",
                        "title": f"implement {filename}", "goal": f"create file {filename}",
                        "checks": [{"kind": "command", "spec": f"test -f {filename}"}]}},
                    {"action": "finish", "args": {}},
                ]
                i = state["top_step"]
                state["top_step"] = i + 1
                return steps[min(i, len(steps) - 1)]
            if not state["wrote"]:
                state["wrote"] = True
                return {"action": "file_edit", "args": {"path": filename, "content": content}}
            return {"action": "finish", "args": {}}
        return {"action": "finish", "args": {}}

    return stub


def test_example_yaml_verification_commands_run_through_scenario_commands(tmp_path):
    examples = [
        ("examples/calc_local_l01.yaml", "calc.py", CALC_EXAMPLE_CONTENT, ["ok"]),
        ("examples/todo_local_l05.yaml", "todo.py", TODO_EXAMPLE_CONTENT,
         ["crud-ok", "persist-ok", "cli-ok"]),
    ]
    for example, filename, content, markers in examples:
        scenario = load_scenario(example)
        result = run_scenario(scenario, runs_dir=tmp_path, run_id=f"test_run_{scenario.name}",
                              model_adapter=StubModel(example_file_stub(filename, content)))
        assert result.status == "done", f"{example}\nrun_dir: {result.run_dir}\nreason: {result.reason}"
        assert len(scenario.verification_commands) == len(markers), example
        for command, marker in zip(scenario.verification_commands, markers):
            assert_final_command_success(result, command, stdout_contains=marker, example=example)


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
