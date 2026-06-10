# Task tools_q10c_byuser_shell_permissions: Tool permissions and shell execution hardening
File name: `tools_q10c_byuser_shell_permissions.md`

## Status

Current status: active
Blocked by: runtime_q10a_byuser_status_score
Description: Make the least-privilege toolset claim true and harden shell execution without
breaking compound acceptance commands.

## Goal

Clarify which tools are universal, which tools are role/phase scoped, and how shell commands are
allowed to run. Verification commands must remain useful, but file writes, command ambiguity, and
permission drift should be explicit and tested.

## Necessary Conditions

- Tool permissions match docs and tests for orchestration, developer, research, verification,
  security, and birthgiver roles.
- Role-specific tool denial is audited and tested.
- Shell execution keeps `&&`, `||`, and pipes working for acceptance checks.
- Shell execution has a documented and tested threat model: cwd allowlist, minimal environment,
  timeout, captured stdout/stderr, and rejected obvious file writes through `bash`.
- Precheck short-circuiting is auditable when a ticket is marked done without a model cycle.

## TODO

### RnD

1. Inspect `PHASE_4_local.md`, `ARCHITECTURE.md`, `src/planfoldr/toolset.py`,
   `src/planfoldr/role.py`, and `src/planfoldr/orchestrator.py::BASE_ROLES` to determine the
   intended permission matrix.

   Verify: write a before/after matrix for orchestration, developer, research, verification,
   security, and birthgiver roles in this quest's Implementation Notes.

2. Inspect `src/planfoldr/tools_impl.py::run_command`, `handle_bash`, `safe_path`, and
   `tests/test_cycle_stub.py::test_run_command_shell_operators_work` to document the current shell
   behavior.

   Verify: record how cwd, env, timeout, stdout/stderr capture, `shell=True`, and write rejection
   currently work.

3. Inspect `src/planfoldr/orchestrator.py::_checks_already_satisfied` and
   `tests/test_e2e_stub.py::test_precheck_short_circuits_already_satisfied_ticket` to understand
   how precheck short-circuiting is currently represented.

   Verify: identify the missing audit/report evidence for a ticket completed by precheck.

### Implementation

4. Decide whether `create_ticket`, `update_ticket`, `write_context`, and `request_decision` are
   universal base tools or role/phase-specific tools; then update `BASE_TOOLS`, role construction,
   docs, and tests to match that decision.

   Verify: `tests/test_toolset.py` asserts the final permission matrix directly, including at
   least one denied role/tool pair that should not be allowed.

5. Keep compound acceptance commands working while documenting the shell threat model in code
   comments or docs. Do not break existing `&&`, `||`, and pipe-based checks.

   Verify: `test_run_command_shell_operators_work` still passes and a doc/comment names the
   deliberate reason compound shell syntax is supported.

6. Strengthen bash write rejection for patterns that matter in this project, without pretending
   regex can fully sandbox a shell. The main control remains workspace cwd, allowlisted cwd, minimal
   env, timeout, and preferring `file_edit` for writes.

   Verify: add focused tests for rejected obvious write patterns and allowed read/check commands.

7. Make command stderr visible to downstream reporting. Ensure command results retain stderr in
   structured form and that verification/tool events include enough stderr for report rendering.

   Verify: add a test command that exits nonzero with stderr and assert the command result and
   emitted audit/tool event contain the stderr text.

8. Make precheck short-circuiting auditable. When `_checks_already_satisfied` marks a ticket done
   without a model cycle, emit a specific audit event or structured note with command, exit code,
   status, and proof source.

   Verify: update `test_precheck_short_circuits_already_satisfied_ticket` to assert short-circuit
   evidence appears in audit and in `tickets.json` or the ticket report page.

### Verification

9. Run the focused tool and cycle tests:
   `.venv/bin/python -m pytest tests/test_toolset.py tests/test_cycle_stub.py -q`.

   Verify: all focused tests pass, including permission denials and shell behavior.

10. Run the focused e2e precheck test:
    `.venv/bin/python -m pytest tests/test_e2e_stub.py::test_precheck_short_circuits_already_satisfied_ticket -q`.

    Verify: the precheck ticket still skips a model cycle and now leaves inspectable audit/report
    evidence.

11. Run the full default suite:
    `.venv/bin/python -m pytest -q`.

    Verify: the full suite passes; record any optional skip count.

12. Inspect generated artifacts from a precheck run: `audit.jsonl`, `tickets.json`, and
    `visibility/tickets.html`.

    Verify: precheck command, exit code/status, ticket id, and proof source are visible.

## Final Verification

- Re-read this quest and confirm every TODO item has implementation evidence or a concrete defer
  note.
- Re-read toolset/shell examples and confirm no pretty examples were removed or weakened.
- Run focused tool/cycle/e2e tests and `.venv/bin/python -m pytest -q`.
- Inspect precheck artifacts directly.
- Move this quest to `quests/done/` only in the same commit that implements and verifies the fixes.

## Implementation Notes

- Split from the original aggregate runtime-hardening quest so permissions and shell behavior can
  be changed without mixing them into status/scoring work.
- Risk anchors:
  - `src/planfoldr/toolset.py::BASE_TOOLS` currently gives every role broad base capabilities.
  - `src/planfoldr/tools_impl.py::run_command` intentionally uses `shell=True` so compound checks
    work.
  - `src/planfoldr/tools_impl.py::handle_bash` rejects only obvious write commands.
  - `src/planfoldr/orchestrator.py::_checks_already_satisfied` marks tickets done without a model
    cycle but needs stronger audit/report evidence.
