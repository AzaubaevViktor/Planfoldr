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
