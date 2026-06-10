# Task tests_q11_byuser_examples_run_commands: Test examples through command execution
File name: `tests_q11_byuser_examples_run_commands.md`

## Status

Current status: completed
Blocked by: none
Description: Update scenario/example tests so behavioral examples are verified by running files
with commands, not by importing modules as a shortcut.

## Goal

Make every example test exercise the same surface a user or acceptance command would exercise:
create files, run command lines, inspect stdout/stderr/files, and avoid import-only checks that can
pass while the executable interface is broken.

## Necessary Conditions

- Example tests must prefer command execution through the scenario's verification commands or an
  equivalent subprocess invocation.
- Import-only checks may remain only as a secondary diagnostic, never as the primary proof that an
  example works.
- Each example's expected behavior must be observable from command exit code, stdout/stderr, or
  generated files.
- The test names and failure messages must point to the example file and command that failed.

## TODO

### RnD

1. Inspect `examples/*.yaml`, `tests/test_e2e_stub.py`, `tests/test_cycle_stub.py`, and any tests
   that load generated files directly to find import-only verification patterns.

   Verify: list every test and example where the current proof is module import, direct function
   call, or direct object inspection instead of running the produced file/CLI.

2. Inspect the example verification commands already stored in scenario YAML files and compare
   them with what tests actually run.

   Verify: produce a table in Implementation Notes with columns: example, intended command,
   current test proof, required replacement.

3. Check whether command execution should go through `run_command`, `subprocess.run`, or the
   scenario runner for each test layer.

   Verify: document the chosen command runner for unit-level, e2e stub-level, and scenario-level
   tests.

### Implementation

4. Replace import-only example assertions with command-based assertions. For each changed test,
   run the generated file or CLI command and assert exit code, stdout/stderr, and output files.

   Verify: intentionally break an executable entry point in a local scratch run or targeted test
   and confirm the updated test fails for the command surface, not only for module import.

5. Preserve all pretty examples and their visible behavior. Do not simplify examples into toy
   imports just to make tests easier.

   Verify: re-read each touched `examples/*.yaml` file and confirm its verification commands and
   user-facing behavior are unchanged unless this quest explicitly documents a correction.

6. Add helper utilities only if they remove real duplication across multiple command-based tests.

   Verify: if a helper is added, at least two tests use it and its failure output includes command,
   cwd, exit code, stdout, and stderr.

### Verification

7. Run focused tests that cover changed examples:
   `.venv/bin/python -m pytest tests/test_e2e_stub.py tests/test_cycle_stub.py -q`.

   Verify: all focused tests pass and at least one changed assertion checks a command exit code.

8. Run the full default suite:
   `.venv/bin/python -m pytest -q`.

   Verify: the full suite passes; record optional skip count if present.

9. Inspect failure readability by reviewing at least one command assertion path in the test code.

   Verify: a failed command would show command, cwd, exit code, stdout, and stderr without raw JSON.

## Final Verification

- Re-read all touched example tests and confirm primary proof is command execution.
- Confirm no pretty examples were removed or weakened.
- Run focused tests and the full default suite.
- Move this quest to `quests/done/` only in the commit that implements and verifies it.

## Implementation Notes

- Created from user request: "Все примеры для тестов надо чтобы проверял не импорт модуля, а запуск
  файла с командами".
- Existing examples were preserved unchanged. The implementation changed the test layer so command
  execution evidence is the primary proof, with direct file/object inspection left only as
  secondary diagnostics.
- Command runner choice:
  - Unit command behavior stays covered through `planfoldr.tools_impl.run_command` in
    `tests/test_cycle_stub.py`.
  - Cycle-level proof uses `Cycle._phase_command_verification`, which records each command in
    `ticket.evidence` with command text, exit code, stdout, and stderr.
  - Scenario/example proof uses `run_scenario` and the final `scenario-verify` ticket, so
    verification commands are executed exactly through the runtime surface a scenario uses.
- Added `assert_ticket_command_success` in `tests/test_cycle_stub.py`; command evidence is now
  asserted before direct file reads in the file-edit/bash and full-code-cycle tests.
- Added `final_command_evidence` and `assert_final_command_success` in `tests/test_e2e_stub.py`.
  Failure messages include run directory, command, status, exit, stdout, and stderr proof.
- Added `test_example_yaml_verification_commands_run_through_scenario_commands` in
  `tests/test_e2e_stub.py`. It loads real example YAML files, has the StubModel create the target
  files, and asserts the example verification commands pass via the final verification ticket.

| example | intended command proof | previous test proof | replacement |
| --- | --- | --- | --- |
| `examples/calc_local_l01.yaml` | scenario command prints `ok` after exercising `calc.py` | no direct example-YAML command test | `run_scenario(load_scenario(...))` writes `calc.py`; `scenario-verify` evidence must contain the exact command, `exit=0`, and stdout marker `ok` |
| `examples/todo_local_l05.yaml` | scenario commands drive `python3 todo.py add/list/done/rm` and print `crud-ok`, `persist-ok`, `cli-ok` | no direct example-YAML command test | `run_scenario(load_scenario(...))` writes `todo.py`; `scenario-verify` evidence must contain each exact YAML command, `exit=0`, and the expected stdout marker |
| stub e2e scenario (`base_scenario`) | final commands `test -f alpha.txt` and `test -f beta.txt` | direct workspace file existence was the primary assertion | `scenario-verify` evidence for both commands is asserted first; workspace file checks remain secondary artifact inspection |
| cycle command tests | ticket check commands such as `test -f solution.py && grep -q VALUE solution.py` | direct file reads and generic success evidence | exact command evidence with `exit=0` is asserted before direct file reads |

- Failure readability was inspected with a scratch broken calc run under
  `runs/test_run_examples_q11_broken_calc`: the final verification failed and `scenario-verify`
  evidence showed the exact `python3 -c ...` command, `exit=1`, and stderr traceback.
- Focused verification:
  `.venv/bin/python -m pytest tests/test_e2e_stub.py tests/test_cycle_stub.py -q` -> 24 passed.
- Full verification:
  `.venv/bin/python -m pytest -q` -> 118 passed, 1 skipped.
