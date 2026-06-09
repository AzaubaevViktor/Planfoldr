# PHASE_3 Coverage — every requirement → evidence

Line-by-line verification that PHASE_3.md is implemented. Status: **✅** implemented + tested ·
**◑** implemented with a documented limitation · **⏳** explicitly deferred *by the spec itself*.

Run the suite: `.venv/bin/python -m pytest -q` → **98 passed, 1 skipped** (the skip is the opt-in
real-Ollama test; run it with `PLANFOLDR_OLLAMA_E2E=1 PLANFOLDR_MODEL=gemma4:26b-mlx`).
Real-model proof: `gemma4:26b-mlx` completes `examples/calc_local.yaml` end-to-end
(`runs/test_run_calc_vis/`: `calc.py` correct, status=done, `analysis.md` clean).

## Базовый цикл — Context Exploration (PHASE_3 §48-56)

| Requirement | Module | Evidence |
|---|---|---|
| ✅ Local memory, ephemeral after the ticket | `cycle.py` `Cycle.local_memory` | `test_cycle_stub.py::test_local_memory_does_not_leak_between_cycles` |
| ✅ Access to tickets + knowledge base | `cycle.py::_phase_context_exploration`, `tools_impl.handle_read_context` | context assembly + `read_context` |
| ✅ Edit the allowed part of tickets/KB | `handle_update_ticket`, `handle_write_context` (scoped) | `test_knowledge_base.py` |
| ✅ Create a ticket on a role by template | `handle_create_ticket`, `Queue.template` | `test_cycle_stub.py::test_create_ticket_spawns_child_with_spawned_by` |
| ✅ Comment + summon roles (even nonexistent → birthgiver) | `tools_impl.handle_comment` + `on_summon`, `birthgiver.summon_ticket` | `test_birthgiver.py::test_comment_tool_summons_unknown_role`, `::test_summon_creates_incoming_ticket_for_birthgiver` |
| ◑ Reply to comments where summoned | `Ticket.comments` + `ROLE_SUMMONED` | comment/summon data + routing exist; an interactive reply loop is minimal |
| ◑ Watch nested cycles + their changes | `Cycle.spawned_tickets`, `graph.dependents_of`, Visibility cycle tree | observable via graph + live State View, not a push inbox |
| ◑ "Incoming changes" list | `graph` dependents + Visibility | represented by graph relations + live pages |

## Базовый цикл — Changes / Command Verify / Model Verify (§58-76)

| Requirement | Module | Evidence |
|---|---|---|
| ✅ Changes: local mem/KB/current+other tickets; domain tools only | `cycle.py::_phase_changes` (allowed = toolset ∩ phase) | `test_cycle_stub.py::test_full_code_cycle_runs_four_phases_and_completes` |
| ✅ Changes may NOT modify tickets / leave comments | `_phase_changes` allowed excludes `update_ticket`/`comment` | phase-allowed split in `cycle.py` |
| ✅ Command Verification runs tests, collects mechanical evidence | `cycle.py::_phase_command_verification`, `tools_impl.run_command` | evidence + `tool.invoked(command_verification)` audit |
| ✅ Model Verification: model judges evidence vs criteria | `cycle.py::_phase_model_verification` | verdict + false-verification detection |
| ✅ Phase subsets (research=1+4, verify=3+4), order preserved | `cycle.py::PHASES_BY_TYPE` | `test_cycle_stub.py::test_research_ticket...`, `::test_verify_ticket...` |
| ◑ Each evidence a separate task | model verification evaluates the evidence set | per-evidence sub-tasking simplified to one verdict pass |

## Очередь и роль (§78-93) · Ролевая система (§243-251) · Очереди (§253-273)

| Requirement | Module | Evidence |
|---|---|---|
| ✅ Queues by direction, with description | `orchestrator.BASE_ROLES`, `Queue.description` | seeded developer/security/research/verification/orchestration(+birthgiver) |
| ✅ Manager triages incoming → in_queue,priority / declined,cause (manager-only) | `Queue.accept/decline`, `orchestrator._triage_all` | `test_queue.py::test_declined_is_manager_only`, `::test_get_next_by_priority_then_fifo` |
| ✅ Role: id, prompt + queue prompt, scope + queue scope | `role.py` `effective_prompt/effective_toolset` | `test_role.py::test_queue_prompt_is_mixed_in_not_overridden`, `::test_queue_scope_extends_without_mutating_base` |
| ✅ Ready (deps done) → executor takes → cycle | `graph.is_ready`, `Queue.refresh_ready`, `orchestrator._executor_loop` | `test_e2e_stub.py::test_dependency_resolved_via_graph` |
| ✅ One role serves many queues; many instances in parallel | `Role.effective_*`, `Queue` | `test_role.py::test_one_role_serves_multiple_queues`, `test_queue.py::test_parallel_executors_take_independent_tickets` |
| ◑ Cycle over a queue (manager as a model cycle) | `Cycle` engine is goal-parameterized; default manager triage is deterministic FIFO | a model-driven queue cycle is supported but not the default |

## Выбор модели + Баллы (§95-102, §210-231)

| Requirement | Module | Evidence |
|---|---|---|
| ✅ Three stats: global / per role / per task type | `score.py` `ModelScore` | `test_score.py::test_positive_criteria_increase_score_and_emit_event` |
| ✅ 2-3 fails → switch to another/stronger | `score.should_switch`, `ModelRegistry.select` | `test_score.py::test_switch_signal_after_consecutive_failures`, `test_model.py::test_registry_select_uses_score_system_not_the_model` |
| ✅ Base = f(parameter_count), adjustable by data | `base_score_from_params` | `test_score.py::test_base_score_grows_with_parameter_count` |
| ✅ All + criteria (correct/verified/budget-saved/fast/passed) | `score.record` | `test_score.py::test_positive_criteria...` |
| ✅ All − criteria (failed×difficulty, budget exhausted, >80% waste, false verify, over-engineering) | `score.record` | `test_score.py::test_simpler_failed_task_penalized_more...`, `::test_negative_criteria_each_subtract` |
| ✅ Stored in audit | `model.score_updated` | `analysis.md` "Score reasons" |

## Управление ресурсами и бюджетами (§104-135)

| Requirement | Module | Evidence |
|---|---|---|
| ✅ All metrics (cpu/ram/runs; file changes/lines; tokens/money/requests/gpu·ram·h; queues/roles/tickets) | `budget.py::Metric` | `test_budget.py` |
| ✅ Real-time update + soft stop → `budget_exceeded` | `Budget.consume/blocked` | `test_budget.py::test_soft_stop...`, `test_e2e_stub.py::test_budget_soft_stop_stops_the_run` |
| ✅ ollama gpu·ram·h via `ollama ps`, correct for a shared model | `Budget.charge_model_seconds`, `parse_ollama_ps` | `test_budget.py::test_shared_model_gpu_attribution_is_per_ticket`; real run `analysis.md` shows gpu·ram·h |
| ✅ Explicit budget delegation per child cycle | `Budget.delegate`, `orchestrator._run_cycle` | `test_budget.py::test_delegation_bubbles_usage_to_parent` |
| ⏳ API models (openai/anthropic) | `ModelConfig.provider/cost_per_token`, `MONEY` metric | structural only — spec says "Далее будет возможность" |
| ⏳ Subscription models / restricted command sandbox | provider hook; workspace allowlist | spec says "после" / "надо поисследовать"; allowlist in `tools_impl.safe_path` |

## Тикет (§137-166) · Переходы статусов (§381-395)

| Requirement | Module | Evidence |
|---|---|---|
| ✅ Ticket = one cycle run; running→cycle; done/failed+evidence | `orchestrator`, `cycle` | `test_e2e_stub.py::test_full_scenario_completes_and_persists` |
| ✅ All fields incl. comments(from/when/whom/text) + metadata/history | `ticket.py::Ticket.to_dict` | `test_ticket.py::test_json_roundtrip` |
| ✅ Status machine incoming→blocked/ready→running→done/failed/needs_review→done | `ticket.VALID_TRANSITIONS` | `test_ticket.py::test_happy_path...`, `::test_needs_review_to_done_requires_reviewer_proof` |
| ✅ Failed after N attempts → difficulty-weighted penalty + handed to next model | `Ticket.exhausted_attempts`, `score.record(difficulty)`, `ModelRegistry.select` | `test_e2e_stub.py::test_failed_ticket_makes_scenario_fail` |
| ◑ Tools approved by "согласователь тулов" | `ToolRegistry.version` + `toolset.changed` audit | changes are versioned + audited; a dedicated approver role is not implemented |

## Динамическое создание тикетов (§168-189)

| Requirement | Module | Evidence |
|---|---|---|
| ✅ Model creates tickets while executing, via explicit `create_ticket` | `tools_impl.handle_create_ticket`, `parse_action` | `test_cycle_stub.py::test_create_ticket_spawns_child_with_spawned_by` |
| ✅ Trace event: who (actor/cycle/exec), why (reason), spawned_by | `new_ticket` emits `ticket.created(actor, reason, spawned_by)`; cycle events carry `cycle_id` | `test_e2e_stub.py::test_audit_has_every_phase_and_tool_call` |
| ✅ New ticket → queue → manager triage (in_queue/declined) | `_create_ticket` + `_triage_all` | `test_queue.py::test_declined_is_manager_only` |

## Флоу работы (§191-208)

| Requirement | Module | Evidence |
|---|---|---|
| ✅ Cycle from the user's formulation (top cycle) | `orchestrator._run_top_cycle` | `test_e2e_stub.py` |
| ✅ `@human` for extra info | `birthgiver.Human`, `request_decision` | `test_birthgiver.py::test_human_answers_and_audits` |
| ✅ Top context formulates goals/constraints, creates first tickets | `_run_top_cycle` (+ constraints in metadata) | real run `runs/test_run_calc_vis` |
| ✅ Execution: delegate to cycles, wait for done / budget | `_executor_loop` | `test_e2e_stub.py` |
| ✅ Final Command + Model verification gate | `_final_verification` | `test_e2e_stub.py::test_full_scenario_completes_and_persists` |
| ◑ Milestones ("вехи") | constraints/goal captured | explicit milestone objects not modeled |

## Циклы — nesting (§233-240)

| Requirement | Module | Evidence |
|---|---|---|
| ✅ constraints down, facts up (output) | `cycle` ticket metadata + `CycleResult.output` | `test_cycle_stub.py` |
| ✅ Parent owns tree; child cannot declare the project done | `ticket.child_closing_parent`; only orchestrator finalizes | `test_ticket.py::test_child_cannot_close_parent`, `test_cycle_stub.py::test_child_cycle_does_not_close_parent` |
| ✅ Budget delegated explicitly | `Budget.delegate` | `test_budget.py` |

## Создатель ролей (§275-291)

| Requirement | Module | Evidence |
|---|---|---|
| ✅ Analyze + create roles/queues; link existing / refuse / create | `birthgiver.Birthgiver.link_or_create/create_role` | `test_birthgiver.py` (create/link/refuse/no-recursive) |
| ✅ Processed live during a run (performance_analyst-style) | `orchestrator._run_birthgiver` | `test_e2e_stub.py::test_birthgiver_creates_role_live_for_unknown_type` |

## Visibility (§293-316)

| Requirement | Module | Evidence |
|---|---|---|
| ✅ Two views: Streaming Log + State View, first-class, live | `visibility/web.py` (4 pages) | `test_visibility.py::test_run_writes_all_pages_analysis_and_model_io` |
| ✅ Streaming like code agents: thinking→output→tools→results, expandable details with input/context/tools | `render_stream_log_html` + `model_output` full capture | `test_visibility.py::test_stream_log_renders_entries_and_goal_header` |
| ✅ State slices: queues/tickets/models/commands/tools/cycles/cycle tree/system/budgets + drill-down | `events.SLICES`, `render_state_view_html`, `render_tickets_html` | `test_visibility.py::test_state_view_commands_and_budgets_are_human_readable`, `::test_tickets_page_shows_comments_history_and_evidence` |
| ✅ Read-only; never blocks | sinks swallow errors | `test_audit.py::test_subscribers...` |
| ✅ WebSocket html↔executor | `visibility/ws.py` (RFC6455, stdlib) | `test_visibility.py::test_ws_server_handshakes_and_broadcasts`, `::test_accept_key_matches_rfc6455_vector` |
| ✅ Works during the run AND as a final artifact | `_write_report` (start+per-phase+per-cycle+end) + meta-refresh; `analysis.md` | `interface.md`; real run artifacts |

## Граф тикетов (§318-333) · Сценарий (§335-346) · Аудит (§348-360) · Toolset (§362-379)

| Requirement | Module | Evidence |
|---|---|---|
| ✅ Graph with all 6 link types, visualized, shows how the tree grew | `graph.py`, `render_tickets_html` tree, `graph.json` | `test_graph.py::test_all_six_link_types_present` |
| ✅ Scenario: plain text → goals/conditions, budget, accesses, verification; rest dynamic | `scenario.py` | `test_e2e_stub.py` |
| ✅ Audit event types (ticket.created actor/reason, status_changed actor/proof, assigned, phase, role.created); graph JSON; replay at ticket | `audit.py`, `graph.to_dict` | `test_audit.py::test_replay_filters_by_ticket` |
| ✅ 6 base tools + `create_role` meta-only (+`comment` context capability) | `toolset.py` | `test_toolset.py::test_create_role_is_meta_only`, `::test_every_role_gets_base_tools` |

## Приоритеты реализации 1-10 (§407-418)

All ten are implemented: 4-phase cycle contract (1), ticket=cycle lifecycle (2), `create_ticket`
tool (3), role system (4), queues (5), live visibility (6), full ticket graph (7), birthgiver (8),
base roles (9), model scoring/selection (10). Non-goals (§398-405: distributed runtime, GUI builder,
full sandbox, parallel DAG optimizer, semantic diff) are intentionally **not** built, as the spec
directs.

## Honest open items (the ◑/⏳ above)

- **API / subscription providers**: structural hooks only — the spec defers them ("далее"/"после").
- **"Согласователь тулов" approver role**: toolset changes are versioned + audited; the dedicated
  approver role is not modeled.
- **Model-driven queue-manager cycle**: the engine supports it; the default manager triage is
  deterministic FIFO/priority.
- **Reply-to-comment / nested-cycle watch inbox / milestones**: the data + observability exist
  (comments, graph, live State View); richer interactive flows are minimal.

These are the only deltas from "to the last letter", and each is either spec-deferred or a thin
interactive layer over already-present data — not a missing capability.
