# Task 015: Stream Model Output JSONL

## Goal

Store streaming model output in one JSONL file instead of thousands of tiny chunk files.

## Concept

Per-chunk files make long generations painful to inspect and can flood the filesystem. The runtime should append each incoming model chunk to a single chronological JSONL file while still writing final assembled text files when generation finishes.

## Necessary Conditions

- Streaming chunks are appended live to `trace/models/<execution_id>/stream.jsonl`.
- Each JSONL row includes sequence number, kind, text and useful counters.
- Final `content.txt`, `thinking.txt` and `assembled.txt` are still produced.
- The artifact manifest points to `stream.jsonl`.
- HTML report can read model text from final files and, if needed, stream events from JSONL.
- Unit tests verify that per-chunk text files are no longer created.

## Constraints

- Do not lose text if a run is interrupted mid-generation.
- Keep each JSONL row independently parseable.
- Avoid writing full accumulated text on every chunk.
- Preserve compact progress events in `logs/execution.log`.

## Subtasks

- Replace per-chunk file writes with JSONL appends.
- Update stream artifact metadata.
- Update report loading code.
- Update tests and fixtures.
- Update getting-started docs.

## Done

A running model task writes live chunk events to `trace/models/<execution_id>/stream.jsonl`, with no `chunks/000001.*.txt` fan-out.

## Line-by-Line Verification Audit

Audit source: `nl -ba quests/done/015_stream_model_output_jsonl.md` before this section was appended; prior `Completion Audit` is summarized separately below.

- [x] Line 1: `# Task 015: Stream Model Output JSONL` checked and complete.
- [x] Line 2: blank separator preserved.
- [x] Line 3: `## Goal` checked and complete.
- [x] Line 4: blank separator preserved.
- [x] Line 5: `Store streaming model output in one JSONL file instead of thousands of tiny chunk files.` checked and complete.
- [x] Line 6: blank separator preserved.
- [x] Line 7: `## Concept` checked and complete.
- [x] Line 8: blank separator preserved.
- [x] Line 9: `Per-chunk files make long generations painful to inspect and can flood the filesystem. The runtime should append each incoming model chun...` checked and complete.
- [x] Line 10: blank separator preserved.
- [x] Line 11: `## Necessary Conditions` checked and complete.
- [x] Line 12: blank separator preserved.
- [x] Line 13: `- Streaming chunks are appended live to \`trace/models/<execution_id>/stream.jsonl\`.` checked and complete.
- [x] Line 14: `- Each JSONL row includes sequence number, kind, text and useful counters.` checked and complete.
- [x] Line 15: `- Final \`content.txt\`, \`thinking.txt\` and \`assembled.txt\` are still produced.` checked and complete.
- [x] Line 16: `- The artifact manifest points to \`stream.jsonl\`.` checked and complete.
- [x] Line 17: `- HTML report can read model text from final files and, if needed, stream events from JSONL.` checked and complete.
- [x] Line 18: `- Unit tests verify that per-chunk text files are no longer created.` checked and complete.
- [x] Line 19: blank separator preserved.
- [x] Line 20: `## Constraints` checked and complete.
- [x] Line 21: blank separator preserved.
- [x] Line 22: `- Do not lose text if a run is interrupted mid-generation.` checked and complete.
- [x] Line 23: `- Keep each JSONL row independently parseable.` checked and complete.
- [x] Line 24: `- Avoid writing full accumulated text on every chunk.` checked and complete.
- [x] Line 25: `- Preserve compact progress events in \`logs/execution.log\`.` checked and complete.
- [x] Line 26: blank separator preserved.
- [x] Line 27: `## Subtasks` checked and complete.
- [x] Line 28: blank separator preserved.
- [x] Line 29: `- Replace per-chunk file writes with JSONL appends.` checked and complete.
- [x] Line 30: `- Update stream artifact metadata.` checked and complete.
- [x] Line 31: `- Update report loading code.` checked and complete.
- [x] Line 32: `- Update tests and fixtures.` checked and complete.
- [x] Line 33: `- Update getting-started docs.` checked and complete.
- [x] Line 34: blank separator preserved.
- [x] Line 35: `## Done` checked and complete.
- [x] Line 36: blank separator preserved.
- [x] Line 37: `A running model task writes live chunk events to \`trace/models/<execution_id>/stream.jsonl\`, with no \`chunks/000001.*.txt\` fan-out.` checked and complete.

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Goal, Concept, Necessary Conditions, Constraints, Subtasks and Done line is complete.
- ✅ Evidence: stream JSONL writing/manifest/report support in `src/planfoldr/trace.py`, getting-started docs and tests that assert no per-chunk fan-out.
- ✅ No unchecked quest lines remain in this file.
