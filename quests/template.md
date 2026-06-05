# Task <module>_<id>: <Title>
File name: `<module>_<id>_<title>.md`

## Status

Current status: blocked / need_info / in_progress / verification / done / ...
Blocked by: <module>_<id>, ...
Description: 

## Goal

State the concrete outcome this quest should achieve in one or two sentences.

## Concept

Explain the current problem, the intended design direction and why this change matters. Keep this section human-readable; it should help the next agent understand the shape of the work before reading code.

## Necessary Conditions

- List observable requirements that must be true when the quest is complete.
- Prefer concrete runtime, artifact, CLI, report or test behavior over vague intent.
- Include compatibility expectations when existing behavior must keep working.

## Constraints

- List boundaries the implementation must respect.
- Call out what must not happen, such as leaking data, writing outside allowed paths or bypassing deterministic runtime controls.
- Keep scope limits here so the quest stays focused.

## Subtasks

- Break the work into small implementation and verification steps.
- Include tests, fixtures or documentation updates when they are part of completion.
- Keep items deterministic enough that an agent can make progress without rereading the whole discussion history.

## Outcome

Describe the final acceptance state in one paragraph. A future agent should be able to read this and know whether the quest can move to `quests/done/`.

## Verification

Self-check questions before deciding that task are done

## Implementation Notes

Use this section only when finishing or handing off a quest. Record important files changed, behavior decisions, verification commands and any remaining follow-up context.
