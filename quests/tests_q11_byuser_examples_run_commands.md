# Task tests_q11_byuser_examples_run_commands: Test examples through command execution
File name: `tests_q11_byuser_examples_run_commands.md`

## Status

Current status: active
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
