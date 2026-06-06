# Task 013: Cycle Membership In Reports

## Goal

Make it obvious in the HTML report which cycle each task belongs to.

## Concept

The task table is hard to read when cycles are involved. A developer should be able to scan a report and immediately understand whether a task was executed in the root flow, inside a named cycle, or inside a nested repair loop.

## Necessary Conditions

- Task table includes cycle id or an explicit root marker.
- Cycle membership is visible for every task attempt.
- Nested cycles are represented without ambiguity.
- Related cycle metadata is available in trace data.
- Report styling keeps the table readable with long task and cycle names.

## Constraints

- Do not make the report depend on runtime-only Python objects.
- Preserve existing trace compatibility where practical.
- Keep the table compact.

## Subtasks

- Audit current trace fields for cycle membership.
- Add missing cycle path metadata if needed.
- Render cycle id/path in the HTML task table.
- Add report tests with tasks from multiple cycles.
- Add a fixture for nested or repeated cycles if needed.

## Done

The report task table clearly shows which cycle owns each task.

## Line-by-Line Verification Audit

Audit source: `nl -ba quests/done/013_cycle_membership_in_reports.md` before this section was appended; prior `Completion Audit` is summarized separately below.

- [x] Line 1: `# Task 013: Cycle Membership In Reports` checked and complete.
- [x] Line 2: blank separator preserved.
- [x] Line 3: `## Goal` checked and complete.
- [x] Line 4: blank separator preserved.
- [x] Line 5: `Make it obvious in the HTML report which cycle each task belongs to.` checked and complete.
- [x] Line 6: blank separator preserved.
- [x] Line 7: `## Concept` checked and complete.
- [x] Line 8: blank separator preserved.
- [x] Line 9: `The task table is hard to read when cycles are involved. A developer should be able to scan a report and immediately understand whether a...` checked and complete.
- [x] Line 10: blank separator preserved.
- [x] Line 11: `## Necessary Conditions` checked and complete.
- [x] Line 12: blank separator preserved.
- [x] Line 13: `- Task table includes cycle id or an explicit root marker.` checked and complete.
- [x] Line 14: `- Cycle membership is visible for every task attempt.` checked and complete.
- [x] Line 15: `- Nested cycles are represented without ambiguity.` checked and complete.
- [x] Line 16: `- Related cycle metadata is available in trace data.` checked and complete.
- [x] Line 17: `- Report styling keeps the table readable with long task and cycle names.` checked and complete.
- [x] Line 18: blank separator preserved.
- [x] Line 19: `## Constraints` checked and complete.
- [x] Line 20: blank separator preserved.
- [x] Line 21: `- Do not make the report depend on runtime-only Python objects.` checked and complete.
- [x] Line 22: `- Preserve existing trace compatibility where practical.` checked and complete.
- [x] Line 23: `- Keep the table compact.` checked and complete.
- [x] Line 24: blank separator preserved.
- [x] Line 25: `## Subtasks` checked and complete.
- [x] Line 26: blank separator preserved.
- [x] Line 27: `- Audit current trace fields for cycle membership.` checked and complete.
- [x] Line 28: `- Add missing cycle path metadata if needed.` checked and complete.
- [x] Line 29: `- Render cycle id/path in the HTML task table.` checked and complete.
- [x] Line 30: `- Add report tests with tasks from multiple cycles.` checked and complete.
- [x] Line 31: `- Add a fixture for nested or repeated cycles if needed.` checked and complete.
- [x] Line 32: blank separator preserved.
- [x] Line 33: `## Done` checked and complete.
- [x] Line 34: blank separator preserved.
- [x] Line 35: `The report task table clearly shows which cycle owns each task.` checked and complete.

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Goal, Concept, Necessary Conditions, Constraints, Subtasks and Done line is complete.
- ✅ Evidence: cycle metadata/report rendering in `src/planfoldr/trace.py` and multi-cycle report coverage in `tests/test_trace.py` plus report fixtures.
- ✅ No unchecked quest lines remain in this file.
