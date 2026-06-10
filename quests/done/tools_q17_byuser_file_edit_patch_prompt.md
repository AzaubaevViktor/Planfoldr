# Task tools_q17_byuser_file_edit_patch_prompt: Teach file_edit patch usage
File name: `tools_q17_byuser_file_edit_patch_prompt.md`

## Status

Current status: done
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

   **Result:** `apply_unified_patch` accepts a standard unified diff. `patch=` fails with
   `ToolError("file_edit: cannot apply patch to a non-existent file")` if the file is missing, and
   `ToolError("patch hunk at line N does not match source: expected ..., got ...")` if context
   lines don't match. Both errors are human-readable and tell the model exactly what went wrong.

2. Inspect `src/planfoldr/cycle.py::_ACTION_REFERENCE` and `_changes_user` for current file-edit
   instructions.

   Verify: identify every prompt sentence that says full file content is required and decide how
   to update it without breaking new-file creation.

   **Result:** `_ACTION_REFERENCE["file_edit"]` showed only full-content mode. `_changes_user`
   contained "CREATE the files needed … (provide the full file content)" implying full-rewrite
   always. Both updated; full-content mode kept as the documented path for new files.

### Implementation

3. Update the `file_edit` action reference to include a patch example using a unified diff and a
   full-content example for new files.

   Verify: captured model prompt includes both examples and clearly says patch existing files for
   small targeted edits.

   **Done:** `_ACTION_REFERENCE["file_edit"]` now documents both modes inline. Prompt inspection
   confirms both `<tool_call>…content…</tool_call>` (full-content) and
   `<tool_call>…patch…</tool_call>` (unified diff) examples are visible to the model, with
   `patch= fails if file does not exist or context lines do not match` guidance.

4. Update changes-phase guidance so models do not always rewrite full files. Keep full content as
   the required mode for creating new files or replacing tiny generated files.

   Verify: prompt tests or captured stub prompts contain "patch existing files" guidance and no
   longer imply full-file overwrite is the only option.

   **Done:** `_changes_user` now reads: "provide full content to create a new file or do a full
   rewrite; use the 'patch' arg with a unified diff to make targeted edits to existing files
   without rewriting them."

5. Add a focused cycle/tool test where an existing file is modified via `file_edit` patch.

   Verify: the file content changes exactly as expected, line-added/removed metrics are correct,
   and audit/tool output names the file and patch result.

   **Done:** `test_file_edit_patch_modifies_existing_file` in `tests/test_cycle_stub.py`
   pre-creates `target.py` with 3 lines, runs a stub cycle that sends a unified-diff patch
   replacing `line2` with `line2_patched`, then asserts:
   - `target.py` reads `"line1\nline2_patched\nline3\n"` exactly
   - audit records `tool.invoked` for `file_edit` with `action=modified`, `lines_added=1`,
     `lines_removed=1`

   Also added `test_patch_mode_documented_in_changes_prompt` which captures the live prompt and
   asserts `"patch"`, `"content"`, and `"existing"` are all present.

### Verification

6. Run tool and cycle tests:
   `.venv/bin/python -m pytest tests/test_cycle_stub.py tests/test_toolset.py -q`.

   Verify: tests pass and include patch-based edit coverage.

   **Result:** 20 passed in 0.13s.

7. Run the full default suite:
   `.venv/bin/python -m pytest -q`.

   Verify: the full suite passes; record optional skip count.

   **Result:** 114 passed, 1 skipped in 1.33s.

8. Inspect a generated prompt from a stub cycle.

   Verify: the model can see both full-content and patch-based `file_edit` examples.

   **Result:** Prompt output confirmed. The ACTION REFERENCE block shows both:
   - full-content: `<tool_call>{"name":"file_edit","arguments":{"path":"...","content":"<FULL file content>"}}</tool_call>`
   - patch: `<tool_call>{"name":"file_edit","arguments":{"path":"...","patch":"--- a/file.py\n+++ b/file.py\n@@ -N,M +N,M @@\n context\n-removed line\n+added line\n context"}}</tool_call>`

## Final Verification

- Patch usage is documented in `_ACTION_REFERENCE["file_edit"]` and in `_changes_user` prose.
- `test_file_edit_patch_modifies_existing_file` exercises the full path through `Cycle` → `Toolset.invoke` → `handle_file_edit` → `apply_unified_patch`.
- `test_patch_mode_documented_in_changes_prompt` confirms the live model prompt exposes both modes.
- Focused tests: 20 passed. Full suite: 114 passed, 1 skipped.

## Implementation Notes

- Created from user request: "научить таки модели делать правки в файл патчом".
- `src/planfoldr/tools_impl.py` already implements `args["patch"]`; the missing piece was prompt
  instruction and behavioral tests — both added.
- `_PROTOCOL` and `_ACTION_REFERENCE` use `<tool_call>` envelope format (updated by
  model_q16_byuser_tool_call_protocol); patch example was written in the same format.
