# Task planning_q19_byuser_priority_table: Active quest priority table
File name: `planning_q19_byuser_priority_table.md`

## Status

Current status: active
Blocked by: none
Description: Prioritize active user-requested quests so simple and important work appears first.

## Goal

Give the next agent a quick ordering view of active quests by complexity and importance.

## Priority Table

Scale: complexity 1 = easiest, 5 = hardest. Importance 1 = lowest, 5 = highest.

| quest | complexity | importance |
|---|---:|---:|
| `tools_q17_byuser_file_edit_patch_prompt.md` | 1 | 5 |
| `visibility_q12_byuser_index_model_json_fallback.md` | 2 | 5 |
| `visibility_q13_byuser_index_tool_call_json.md` | 2 | 4 |
| `model_q16_byuser_tool_call_protocol.md` | 3 | 5 |
| `visibility_q18_byuser_internal_thinking_summary.md` | 3 | 5 |
| `visibility_q15_byuser_index_last_result_json.md` | 3 | 4 |
| `tests_q11_byuser_examples_run_commands.md` | 3 | 4 |
| `runtime_q10a_byuser_status_score.md` | 5 | 5 |
| `visibility_q14_byuser_index_raw_prompt_json.md` | 4 | 4 |
| `visibility_q10b_byuser_report_hardening.md` | 4 | 4 |
| `tools_q10c_byuser_shell_permissions.md` | 4 | 3 |

## Dependency Notes

- `visibility_q13_byuser_index_tool_call_json.md` is blocked by
  `visibility_q12_byuser_index_model_json_fallback.md`.
- `tools_q17_byuser_file_edit_patch_prompt.md` is blocked by
  `model_q16_byuser_tool_call_protocol.md`; it is listed first because it is the smallest
  high-value quest once that dependency is cleared.
- `visibility_q18_byuser_internal_thinking_summary.md` is blocked by
  `model_q16_byuser_tool_call_protocol.md`.
- `visibility_q10b_byuser_report_hardening.md` and `tools_q10c_byuser_shell_permissions.md` are
  blocked by `runtime_q10a_byuser_status_score.md`.

## Final Verification

- Re-read the active quest list under `quests/` and confirm every active implementation quest,
  excluding this planning artifact, appears once in the table.
- Confirm filenames use the `[module]_[id]_byuser_[short_info].md` pattern.
- Re-sort this table whenever a quest is moved to `quests/done/` or a new active quest is added.

## Implementation Notes

- Created from user request: "Давай сделаем табличку (квест; сложность; важность) где простые и
  важные будут выше".
- This is a planning artifact; it does not replace each quest's own TODO and verification details.
