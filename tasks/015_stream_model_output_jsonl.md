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
