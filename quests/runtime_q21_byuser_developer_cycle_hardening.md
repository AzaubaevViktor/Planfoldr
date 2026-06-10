# Task runtime_q21_byuser_developer_cycle_hardening: Hardening developer cycle — iteration waste and context loss
File name: `runtime_q21_byuser_developer_cycle_hardening.md`

## Status

Current status: active
Blocked by: none
Description: Observed in the 2026-06-10_23-03-17 run (taskmanager_local_l10b / gemma4:31b).
The developer cycle burned all 8 iterations but wrote only 1 of 8 required files.
The model re-planned from scratch at every iteration because it couldn't see what it had
already written. Repeated bash `mkdir` calls and duplicate `file_edit` triggered the
no-progress detector and killed the loop before any real work was done.

## Concrete failure observed

Run `taskmanager_local_l10b.yaml` with `gemma4:31b`, developer-1 cycle:

| Iteration | Action | Result |
|---|---|---|
| 1 | `plan` (context_exploration) | ok, not preserved |
| 2 | `bash mkdir -p tasks` | exit=0, productive |
| 3 | `bash mkdir -p tasks` | exit=0, **sig repeat** |
| 4 | `file_edit tasks/model.py` | created, path_edits=1 |
| 5 | `bash mkdir -p tasks` | exit=0, productive=False (bash cmd result) |
| 6 | `file_edit tasks/model.py` | path_edits=2 → productive=False, no_progress=2 → **loop exits** |

Result: 8 iterations burned, only `tasks/model.py` written (twice), 7 files missing.
Score: -12 (failed). No `tasks/filter.py`, `tasks/store.py`, etc. ever created.

## Root causes

### RC-1: Model doesn't see what it has already done in this cycle

`_changes_user` shows only `Last tool result` — the single last action's output.
The model has no running list of files already written in this cycle. At each new iteration
it starts over with its full planning thought, re-inventing the same plan, then re-doing the
first step. The `changes_log` is accumulated in `local_memory` but never surfaced in the prompt.

### RC-2: `max_iterations=8` is too low for multi-file tickets

An 8-file project needs at minimum 8 `file_edit` actions plus 1 `plan` plus 1 `bash` for
tests = 10 actions. With any wasted iterations (repeated mkdir, protocol errors, reformat
retries) the budget runs out mid-way. Planning tickets only get `max_iterations=4`, which is
fine. But code tickets with many files need headroom.

### RC-3: No-progress detector penalises consecutive `bash` and re-edit

The no-progress logic marks `bash` calls as `productive=False` when there's no meaningful
result (e.g. `mkdir` when dir already exists has `exit=0` but no output — same as a
no-op). This is correct, but the check currently fires on any bash result, including the
FIRST mkdir that was genuinely needed. Combined with `path_edits[fp] <= 1` (second write to
a file = unproductive), the detector is too aggressive for iterative development where the
model might need to fix a file it just created.

### RC-4: `plan` output is lost between phases

The developer cycle runs `context_exploration` first (1 iteration, `plan` action). The
plan goes into `local_memory["plan"]`. Then `changes` starts fresh with a new `_changes_user`
prompt that doesn't include the plan. The model re-plans again at the start of changes,
burning another iteration on the same output.

### RC-5: `bash` used for `mkdir` instead of relying on `file_edit`

The prompt allows `bash` but doesn't tell the model that `file_edit` creates parent
directories automatically. The model wastes 1-3 iterations on `mkdir -p` calls that are
never needed.

### RC-6: Orchestration creates the same ticket twice in one action loop

In context_exploration (max_iterations=1) the model did `plan` (one action, loop exits).
In changes the model created the same ticket twice. Dedup returned `developer-1` for both.
`spawned_tickets` records `['developer-1', 'developer-1']` — a cosmetic bug, harmless but
noisy in the report.

## Necessary Conditions

- A developer cycle working on an 8-file project must be able to write all 8 files before
  hitting the iteration cap.
- The model must see a running "changes so far" block in every iteration of the changes
  loop so it can pick up where it left off without re-planning.
- The `plan` from context_exploration must be visible in the changes loop.
- The no-progress detector must allow a model to write a file once, run a verification bash
  command, and fix the file if the command failed — without counting that as "no progress".
- `spawned_tickets` must not list the same ticket id twice.

## TODO

### RnD

1. Re-read `src/planfoldr/cycle.py::_changes_user` and `_action_loop` to confirm:
   (a) which fields from `local_memory` are surfaced in the user prompt,
   (b) how `changes_log` is built and where it is discarded,
   (c) what `no_progress` and `path_edits` count exactly.

   Verify: note the exact line numbers and field names.

2. Re-read `src/planfoldr/cycle.py::_phase_context_exploration` and confirm that the
   `plan` output from context is NOT carried into the changes prompt.

   Verify: trace `local_memory["plan"]` from set to discard.

3. Check `src/planfoldr/orchestrator.py::_run_cycle` for the `max_iterations` values
   assigned to planning vs code tickets.

   Verify: record the current values for `is_planning` True and False branches.

### Implementation

4. Add a "changes so far" block to `_changes_user`. When `local_memory["changes_log"]`
   is non-empty, include a compact summary at the top of the user prompt:

   ```
   ALREADY DONE IN THIS CYCLE:
   - file_edit tasks/model.py → created (12 lines)
   - bash mkdir -p tasks → exit=0
   ```

   Show only the action name, path/cmd (truncated to 60 chars), and result status.
   Cap the list at the last 10 entries to avoid flooding the prompt.

   Verify: add `tests/test_cycle_stub.py::test_changes_user_includes_changes_log` — run
   a two-action stub sequence, assert the second call's user prompt contains "ALREADY DONE"
   with the first action listed.

5. Carry the `plan` from context_exploration into the changes prompt. When
   `local_memory.get("plan")` is set, include it as a one-liner at the top of the changes
   user prompt:

   ```
   PLAN: <first plan entry, truncated to 200 chars>
   ```

   Verify: add `tests/test_cycle_stub.py::test_changes_user_includes_plan` — assert the
   plan text appears in the changes prompt when local_memory["plan"] is set.

6. Raise `max_iterations` for code/fix/tests tickets to 16 (from 8). Keep planning tickets
   at 4. Document the rationale in a comment.

   Verify: update any test that asserts `max_iterations=8`; confirm the e2e stub still
   terminates in bounded time.

7. Relax the no-progress detector for `file_edit`:
   - Allow a file to be edited up to 2 times before counting as unproductive (change
     `path_edits[fp] <= 1` to `path_edits[fp] <= 2`).
   - Mark `bash` as productive when `exit_code == 0` AND `stdout` is non-empty, OR when
     `exit_code != 0` (i.e. a test failure is genuine progress — the model learned something).
   - Keep the full repeated-identical-action guard (`sig == last_sig` for 2+ in a row).

   Verify: add a focused test where a file_edit on the same path twice counts as productive
   for the first two writes; assert the third write is unproductive.

8. Add a sentence to `_changes_user` in the ACTION REFERENCE preamble:
   "file_edit creates parent directories automatically — never use bash mkdir."

   Verify: confirm the sentence appears in the prompt text from `_changes_user`.

9. Fix duplicate entry in `spawned_tickets`. In `_wrap_create_ticket`, when dedup returns
   an existing ticket id (i.e. `fn(spec)` returns an id already in `self.spawned_tickets`),
   do not append it again.

   Verify: add `tests/test_cycle_stub.py::test_no_duplicate_spawned_ticket_ids` — create
   the same ticket spec twice via the orchestrator; assert `spawned_tickets` contains the
   id exactly once and `cycle_result.spawned_tickets` has no duplicates.

### Verification

10. Run focused cycle tests:
    `.venv/bin/python -m pytest tests/test_cycle_stub.py -q`.

    Verify: all new tests pass, no existing tests regress.

11. Run full suite:
    `.venv/bin/python -m pytest -q`.

    Verify: all tests pass.

12. Re-run `taskmanager_local_l10b.yaml` (or any multi-file scenario) with `gemma4:31b`
    and confirm in the terminal output that:
    - The "ALREADY DONE" block appears from the second iteration onward.
    - The developer cycle writes more than 1 file before the loop exits.
    - `spawned_tickets` in the terminal shows no duplicates.

## Final Verification

- Re-read this quest and confirm every TODO item has implementation evidence or a defer note.
- Re-read `AGENTS.md` examples and confirm no pretty examples were removed.
- Run focused cycle tests and `.venv/bin/python -m pytest -q`.
- In a re-run of the scenario, inspect terminal output and `model_io.jsonl` to confirm the
  model writes multiple files in one cycle.
- Move to `quests/done/` only in the same commit that passes all tests and re-run.

## Implementation Notes

Observed run: `runs/2026-06-10_23-03-17__run_f47dc88cab3b` (taskmanager_local_l10b / gemma4:31b).

- Tool call sequence in developer-1 changes loop:
  `mkdir` → `mkdir` → `file_edit model.py` → `mkdir` → `file_edit model.py` → **no_progress=2 exit**
- Only `runs/.../workspace/tasks/model.py` was written; 7 files missing.
- `model_io.jsonl` shows thinking_len >> content_len on most iterations — model spends most
  tokens re-planning rather than executing.
- Thinking tokens per call: [5514, 3659, 5622, 891, 867, 682, 1450, 2984, 318, 958] — total
  ~22K chars of thinking for ~10K chars of actual action content.
- Fix priority: RC-1 (missing changes_log in prompt) and RC-2 (max_iterations too low) have
  the highest expected impact and are independent of each other.
