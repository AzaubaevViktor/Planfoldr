# Task model_001: Use Model Tool-Call Syntax
File name: `model_001_use_tool_call_syntax.md`

## Status

Current status: ready
Blocked by: none
Description: Ready to implement `<tool_call>` parsing at the model output boundary.

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

Not started.
