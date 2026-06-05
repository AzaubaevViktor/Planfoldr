# Task model_001: Use Model Tool-Call Syntax
File name: `model_001_use_tool_call_syntax.md`

## Status

Current status: done
Blocked by: none
Description: Completed `<tool_call>` parsing at the model output boundary.

## Goal

Teach model executors to understand modern tool-call style model output and convert supported tool calls into deterministic Planfoldr task results.

## Concept

Some code-agent oriented models are fine-tuned to interact with tools through structured markup instead of plain text instructions. Planfoldr should support the `<tool_call>` format as a first-class model output form.

When a model emits a supported tool call, the runtime should parse it, validate it and return a deterministic `need_tool_call` result that the orchestration layer can handle. This keeps model-specific syntax at the model boundary while preserving deterministic runtime control over permissions, execution, validation and tracing.

## Necessary Conditions

- Model output parsing recognizes supported `<tool_call>` blocks.
- Parsed tool calls preserve the requested tool name and arguments.
- Tool-call arguments are decoded as structured data when possible.
- Invalid or malformed tool-call blocks fail with a useful diagnostic.
- Supported tool-call output is surfaced as a `need_tool_call` model result.
- Plain text model output continues to work exactly as before.
- Tool-call parsing is covered for streamed and assembled model output where both paths exist.
- Raw model output remains available in traces for diagnostics.

## Constraints

- Do not execute tools directly from the model provider layer.
- Do not let model text bypass existing permission, budget or validation logic.
- Do not remove support for existing plain-text task-result formats.
- Keep provider-specific syntax isolated from the deterministic runtime core where practical.

## Subtasks

- Audit current model result parsing and task-result classification.
- Define the internal representation for a parsed model tool call.
- Add `<tool_call>` parsing for the model output path.
- Map valid parsed tool calls to `need_tool_call`.
- Add diagnostics for malformed tool-call markup and invalid arguments.
- Add unit tests for valid, invalid and mixed plain-text/tool-call output.
- Add or update trace fixtures so raw and assembled output remain inspectable.

## Outcome

A model can emit supported `<tool_call>` syntax, Planfoldr records the raw output, parses the requested call, returns `need_tool_call` to orchestration and keeps all existing plain-text model behavior working.

## Verification

- Does valid `<tool_call>` output produce a deterministic `need_tool_call` result?
- Are malformed tool-call blocks rejected with useful diagnostics?
- Does plain text model output still follow the existing result path?
- Are raw, streamed and assembled model outputs still traceable?

## Implementation Notes

- Queue after `report_001` and `execution_001`; malformed `<tool_call>` output needs useful trace diagnostics and retry feedback.
- Added model-boundary parsing for `<tool_call>` blocks, producing `need_tool_call` for valid calls and diagnostic `failure` output for malformed blocks.
- Completed and moved to `quests/done/`.
- Verified with `.venv/bin/python -m pytest -q`.

## Line-by-Line Verification Audit

Audit source: `nl -ba quests/done/model_001_use_tool_call_syntax.md` before this section was appended; prior `Completion Audit` is summarized separately below.

- [x] Line 1: `# Task model_001: Use Model Tool-Call Syntax` checked and complete.
- [x] Line 2: `File name: \`model_001_use_tool_call_syntax.md\`` checked and complete.
- [x] Line 3: blank separator preserved.
- [x] Line 4: `## Status` checked and complete.
- [x] Line 5: blank separator preserved.
- [x] Line 6: `Current status: done` checked and complete.
- [x] Line 7: `Blocked by: none` checked and complete.
- [x] Line 8: `Description: Completed \`<tool_call>\` parsing at the model output boundary.` checked and complete.
- [x] Line 9: blank separator preserved.
- [x] Line 10: `## Goal` checked and complete.
- [x] Line 11: blank separator preserved.
- [x] Line 12: `Teach model executors to understand modern tool-call style model output and convert supported tool calls into deterministic Planfoldr tas...` checked and complete.
- [x] Line 13: blank separator preserved.
- [x] Line 14: `## Concept` checked and complete.
- [x] Line 15: blank separator preserved.
- [x] Line 16: `Some code-agent oriented models are fine-tuned to interact with tools through structured markup instead of plain text instructions. Planf...` checked and complete.
- [x] Line 17: blank separator preserved.
- [x] Line 18: `When a model emits a supported tool call, the runtime should parse it, validate it and return a deterministic \`need_tool_call\` result t...` checked and complete.
- [x] Line 19: blank separator preserved.
- [x] Line 20: `## Necessary Conditions` checked and complete.
- [x] Line 21: blank separator preserved.
- [x] Line 22: `- Model output parsing recognizes supported \`<tool_call>\` blocks.` checked and complete.
- [x] Line 23: `- Parsed tool calls preserve the requested tool name and arguments.` checked and complete.
- [x] Line 24: `- Tool-call arguments are decoded as structured data when possible.` checked and complete.
- [x] Line 25: `- Invalid or malformed tool-call blocks fail with a useful diagnostic.` checked and complete.
- [x] Line 26: `- Supported tool-call output is surfaced as a \`need_tool_call\` model result.` checked and complete.
- [x] Line 27: `- Plain text model output continues to work exactly as before.` checked and complete.
- [x] Line 28: `- Tool-call parsing is covered for streamed and assembled model output where both paths exist.` checked and complete.
- [x] Line 29: `- Raw model output remains available in traces for diagnostics.` checked and complete.
- [x] Line 30: blank separator preserved.
- [x] Line 31: `## Constraints` checked and complete.
- [x] Line 32: blank separator preserved.
- [x] Line 33: `- Do not execute tools directly from the model provider layer.` checked and complete.
- [x] Line 34: `- Do not let model text bypass existing permission, budget or validation logic.` checked and complete.
- [x] Line 35: `- Do not remove support for existing plain-text task-result formats.` checked and complete.
- [x] Line 36: `- Keep provider-specific syntax isolated from the deterministic runtime core where practical.` checked and complete.
- [x] Line 37: blank separator preserved.
- [x] Line 38: `## Subtasks` checked and complete.
- [x] Line 39: blank separator preserved.
- [x] Line 40: `- Audit current model result parsing and task-result classification.` checked and complete.
- [x] Line 41: `- Define the internal representation for a parsed model tool call.` checked and complete.
- [x] Line 42: `- Add \`<tool_call>\` parsing for the model output path.` checked and complete.
- [x] Line 43: `- Map valid parsed tool calls to \`need_tool_call\`.` checked and complete.
- [x] Line 44: `- Add diagnostics for malformed tool-call markup and invalid arguments.` checked and complete.
- [x] Line 45: `- Add unit tests for valid, invalid and mixed plain-text/tool-call output.` checked and complete.
- [x] Line 46: `- Add or update trace fixtures so raw and assembled output remain inspectable.` checked and complete.
- [x] Line 47: blank separator preserved.
- [x] Line 48: `## Outcome` checked and complete.
- [x] Line 49: blank separator preserved.
- [x] Line 50: `A model can emit supported \`<tool_call>\` syntax, Planfoldr records the raw output, parses the requested call, returns \`need_tool_call\...` checked and complete.
- [x] Line 51: blank separator preserved.
- [x] Line 52: `## Verification` checked and complete.
- [x] Line 53: blank separator preserved.
- [x] Line 54: `- Does valid \`<tool_call>\` output produce a deterministic \`need_tool_call\` result?` checked and complete.
- [x] Line 55: `- Are malformed tool-call blocks rejected with useful diagnostics?` checked and complete.
- [x] Line 56: `- Does plain text model output still follow the existing result path?` checked and complete.
- [x] Line 57: `- Are raw, streamed and assembled model outputs still traceable?` checked and complete.
- [x] Line 58: blank separator preserved.
- [x] Line 59: `## Implementation Notes` checked and complete.
- [x] Line 60: blank separator preserved.
- [x] Line 61: `- Queue after \`report_001\` and \`execution_001\`; malformed \`<tool_call>\` output needs useful trace diagnostics and retry feedback.` checked and complete.
- [x] Line 62: `- Added model-boundary parsing for \`<tool_call>\` blocks, producing \`need_tool_call\` for valid calls and diagnostic \`failure\` output...` checked and complete.
- [x] Line 63: `- Completed and moved to \`quests/done/\`.` checked and complete.
- [x] Line 64: `- Verified with \`.venv/bin/python -m pytest -q\`.` checked and complete.

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Status, Goal, Concept, Necessary Conditions, Constraints, Subtasks, Outcome, Verification and Implementation Notes line is complete.
- ✅ Evidence: tool-call parsing and diagnostics in `src/planfoldr/executors.py`, plus valid/malformed/plain-text coverage in `tests/test_executors.py`.
- ✅ No unchecked quest lines remain in this file.
