# Task tools_q17_byuser_file_edit_patch_prompt: Teach file_edit patch usage
File name: `tools_q17_byuser_file_edit_patch_prompt.md`

## Status

Current status: active
Blocked by: model_q16_byuser_tool_call_protocol
Description: `file_edit` supports unified-diff patches, but the model-facing instructions still
primarily teach full-file overwrite.

## Goal

Teach models when and how to patch existing files with `file_edit` instead of rewriting whole
files, while preserving full-content creation for new files.

## Necessary Conditions

- `file_edit` action reference must document both creation/full overwrite and patch modes.
- Prompt guidance must tell the model to use patches for targeted edits to existing files.
- Tests must prove a model can edit an existing file by sending a patch through the tool protocol.
- Patch failures must produce readable feedback that helps the model retry.

## TODO

### RnD

1. Inspect `src/planfoldr/tools_impl.py::handle_file_edit` and `apply_unified_patch` to document
   the exact patch argument format and failure modes.

   Verify: record whether patch is unified diff, whether the file must exist, and what error is
   returned when context does not match.

2. Inspect `src/planfoldr/cycle.py::_ACTION_REFERENCE` and `_changes_user` for current file-edit
   instructions.

   Verify: identify every prompt sentence that says full file content is required and decide how
   to update it without breaking new-file creation.

### Implementation

3. Update the `file_edit` action reference to include a patch example using a unified diff and a
   full-content example for new files.

   Verify: captured model prompt includes both examples and clearly says patch existing files for
   small targeted edits.

4. Update changes-phase guidance so models do not always rewrite full files. Keep full content as
   the required mode for creating new files or replacing tiny generated files.

   Verify: prompt tests or captured stub prompts contain "patch existing files" guidance and no
   longer imply full-file overwrite is the only option.

5. Add a focused cycle/tool test where an existing file is modified via `file_edit` patch.

   Verify: the file content changes exactly as expected, line-added/removed metrics are correct,
   and audit/tool output names the file and patch result.

### Verification

6. Run tool and cycle tests:
   `.venv/bin/python -m pytest tests/test_cycle_stub.py tests/test_toolset.py -q`.

   Verify: tests pass and include patch-based edit coverage.

7. Run the full default suite:
   `.venv/bin/python -m pytest -q`.

   Verify: the full suite passes; record optional skip count.

8. Inspect a generated prompt from a stub cycle.

   Verify: the model can see both full-content and patch-based `file_edit` examples.

## Final Verification

- Confirm patch usage is documented in model-facing prompts and tested through tool execution.
- Run focused tests and full suite.
- Move this quest to `quests/done/` only after implementation and verification.

## Implementation Notes

- Created from user request: "научить таки модели делать правки в файл патчом".
- `src/planfoldr/tools_impl.py` already implements `args["patch"]`; the missing piece is prompt
  instruction and behavioral tests.
