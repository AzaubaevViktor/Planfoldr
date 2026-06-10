# Task runtime_q20_byuser_orchestration_zero_spawn: Guard against zero-spawn orchestration
File name: `runtime_q20_byuser_orchestration_zero_spawn.md`

## Status

Current status: active
Blocked by: none
Description: An orchestration cycle that spawns zero sub-tickets is always marked `done`
because the orchestration ticket type skips both verification phases, making `passed=True`
unconditionally. When a model returns empty content (e.g. HTTP 500 from a model that
cannot handle `<tool_call>` in the system prompt), the orchestration silently "succeeds"
with no work queued, the executor loop finds nothing to do, and final verification fails
on every command because no code was written. The failure is invisible until the very end.

## Goal

Make zero-spawn orchestration a detectable, reported, and recoverable harness failure
rather than a silent false success.

## Concrete failure observed

Run `mini_httpd_local_l14.yaml` with `qwen3-coder:30b`:
- `qwen3-coder:30b` crashes with HTTP 500 on any prompt containing `<tool_call>` XML.
- `OllamaModel.generate()` catches the HTTPError as OSError and returns
  `ModelResponse(content="", available=False, tokens=0)`.
- The action loop receives parse errors for all 4 iterations, burns reformat retries, exits.
- `_finalize` for an `orchestration` type ticket: `cmd_ok=True, model_ok=True, passed=True`
  (no verification phases run for orchestration), so ticket → `done`, score +4.
- `_executor_loop` finds 0 ready tickets, exits immediately.
- Final verification runs 11 commands, all fail (nothing was built).
- `analysis.md` calls it "failed" but the root cause — orchestration with zero spawned tickets
  — is not named.

## Necessary Conditions

- An orchestration cycle that completes with zero spawned tickets must NOT be marked `done`.
  It must be retried (up to `max_attempts`) or, on exhaustion, fail with a clear reason.
- When a model call returns `available=False` or empty content, the error must be surfaced
  in the terminal stream and in `audit.jsonl` as a named event, not silently swallowed.
- The terminal output must show a warning line when any model call in a cycle returns empty
  content (e.g. `⚠️  model returned empty response (available=False): <reason>`).
- `analysis.md` must list zero-spawn orchestration as a distinct failure signature with the
  responsible model and the HTTP error reason when known.

## TODO

### RnD

1. Re-read `src/planfoldr/cycle.py::_finalize` and `PHASES_BY_TYPE` to confirm why
   orchestration tickets always pass regardless of model output.

   Verify: record the exact line numbers and variable values (`cmd_ok`, `model_ok`, `passed`)
   for the orchestration type in this quest's Implementation Notes.

2. Re-read `src/planfoldr/model.py::OllamaModel.generate()` to confirm what is returned when
   the model raises `HTTPError` or `URLError`, and what `response.available` and `response.raw`
   contain.

   Verify: note the exact return path and which fields carry the error reason.

3. Re-read `src/planfoldr/cycle.py::_action_loop` and `_one_action` to confirm that empty
   content and `available=False` are treated the same as a parse error (reformat retry),
   and that there is no early exit or escalation on connection failure.

   Verify: record the reformat-retry path and confirm that `available=False` is never checked.

4. Re-read `src/planfoldr/orchestrator.py::_run_top_cycle` and `_executor_loop` to confirm
   that zero spawned tickets causes the executor loop to exit immediately without any diagnostic.

   Verify: trace the `spawned_tickets == []` path from `_run_top_cycle` through `_executor_loop`
   to `_final_verification`.

5. Check `src/planfoldr/visibility/analysis.py::build_analysis` and the `analysis.md` from the
   failing run at `runs/2026-06-10_22-53-07__run_2ea4f9c9cb4a/analysis.md` to confirm that
   zero-spawn orchestration is not named as a failure signature.

   Verify: record which failure signatures are currently detected and which are not.

### Implementation

6. In `src/planfoldr/cycle.py::_finalize`, add a zero-spawn guard for orchestration type
   tickets: if `self.ticket.type in ("orchestration", "decompose", "plan")` and
   `len(self.spawned_tickets) == 0` and the cycle was not budget-exceeded, do not mark the
   ticket `done` — instead mark it `needs_review` with reason
   `"orchestration produced no tickets; retry"`.

   The score must not receive a success bonus on this path. Preserve the existing `passed=True`
   logic for the case where the ticket type legitimately needs no spawned tickets (i.e. add a
   predicate, not a blanket type check).

   Verify: add `tests/test_cycle_stub.py::test_orchestration_zero_spawn_needs_review` — use
   a StubModel that returns `plan` actions but never `create_ticket`; assert the cycle result
   is `needs_review`, score receives no success bonus, and reason contains "no tickets".

7. In `src/planfoldr/cycle.py::_one_action`, check `response.available` immediately after
   `self.model.generate()`. When `available=False`, emit a distinct stream event
   `"model_unavailable"` with `reason=response.raw` (the error string), and return
   `Action(action="", error=f"model unavailable: {response.raw}")` without burning a reformat
   retry.

   Verify: add `tests/test_cycle_stub.py::test_model_unavailable_returns_error_action` — use
   a ModelAdapter subclass that returns `ModelResponse(available=False, raw="HTTP 500")`;
   assert the returned Action has `error` set, no reformat retries are consumed, and the
   stream_sink receives a `"model_unavailable"` event with the reason.

8. In `src/planfoldr/visibility/terminal.py` (or wherever terminal stream events are rendered),
   add a handler for `"model_unavailable"` events that prints a visible warning line, e.g.:
   `│  ⚠️  model unavailable: HTTP Error 500: Internal Server Error`.

   Verify: add a test or manual check that confirms the warning appears in terminal output when
   the model returns `available=False`.

9. In `src/planfoldr/visibility/analysis.py::build_analysis`, add detection for the
   zero-spawn-orchestration failure signature: when an orchestration ticket is `needs_review`
   or `failed`, and its spawned-ticket count is 0, emit a named failure signature
   `"zero_spawn_orchestration"` with the cycle id, model, and any model_unavailable reason
   from the audit log.

   Verify: run the stub scenario from TODO 6 and confirm `analysis.md` lists
   `zero_spawn_orchestration` under "What went wrong".

### Verification

10. Run focused cycle tests:
    `.venv/bin/python -m pytest tests/test_cycle_stub.py -q -k "orchestration or unavailable"`.

    Verify: both new tests pass; no existing cycle tests regress.

11. Run the full default suite:
    `.venv/bin/python -m pytest -q`.

    Verify: all tests pass; record any optional Ollama skip count.

12. Run the stub e2e scenario and inspect the run directory artifacts:
    `.venv/bin/python -m pytest tests/test_e2e_stub.py -q`.

    Verify: `result.json` status and reason, `tickets.json` orchestration ticket status,
    and `analysis.md` zero-spawn signature are all present and consistent.

## Final Verification

- Re-read this quest and confirm every TODO item has implementation evidence or a concrete
  defer note.
- Re-read `AGENTS.md` examples and confirm no pretty examples were removed.
- Run focused cycle tests and `.venv/bin/python -m pytest -q`.
- Inspect at least one generated run's `analysis.md` and `result.json` directly.
- Move this quest to `quests/done/` only in the same commit that implements and verifies fixes.

## Implementation Notes

Root cause (confirmed by investigation on 2026-06-10):

- `src/planfoldr/cycle.py::PHASES_BY_TYPE["orchestration"] = [CONTEXT, CHANGES]` — no
  verification phases, so `_finalize` always computes `cmd_ok=True, model_ok=True, passed=True`.
- `src/planfoldr/model.py::OllamaModel.generate()` lines 243-246 — HTTPError caught as OSError,
  returns `ModelResponse(content="", available=False, raw=str(exc))`.
- `src/planfoldr/cycle.py::_one_action` — never checks `response.available`; parse_action("")
  returns an error Action, which burns a reformat retry but does not escalate.
- `src/planfoldr/orchestrator.py::_run_top_cycle` calls `_run_cycle` and discards the result;
  `_executor_loop` then finds no ready tickets and exits silently.
- Confirmed trigger: `qwen3-coder:30b` returns HTTP 500 whenever `<tool_call>` appears in
  the system message — the harness always includes it in `_PROTOCOL`.
- The fix must not change the passing behavior of orchestration tickets that correctly spawn
  tickets (the common case); it only catches the zero-spawn edge case.
