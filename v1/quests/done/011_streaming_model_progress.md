# Task 011: Streaming Model Progress

## Goal

Add streaming model execution so long Ollama calls visibly make progress while they run.

## Concept

Current model execution uses a blocking Ollama request. During slow local-model runs, `logs/execution.log` only shows `task_start` and then nothing until timeout or completion. The runtime should stream model chunks, count progress as it arrives and write live log events so a developer can see that generation is active.

## Necessary Conditions

- Ollama adapter can use streaming API responses.
- Model streaming progress is written to `logs/execution.log` while the task is still running.
- Progress events include task id, attempt number and cumulative generated text length.
- Progress events include token counts when the provider reports them.
- If exact token counts are unavailable mid-stream, log an explicit approximate counter or `unsupported` marker.
- Final model metadata captures streaming stats.
- Timeouts still return a structured `failure` or `retry_exceeded` result.
- Existing non-streaming tests remain deterministic.

## Constraints

- Do not require network or Ollama for regular unit tests.
- Do not dump full model text into every progress log event.
- Keep `execution.log` useful and compact.
- Do not let streaming output drive links before output validation passes.
- Preserve existing trace/report artifact layout.

## Proposed Events

Append JSONL events like:

```json
{"event":"model_stream_start","task_id":"generate_project","attempt":1}
{"event":"model_stream_progress","task_id":"generate_project","attempt":1,"chars":2048,"tokens":{"generated":256,"source":"approximate"}}
{"event":"model_stream_finish","task_id":"generate_project","attempt":1,"chars":8192,"tokens":{"generated":1024,"source":"provider"}}
```

## Subtasks

- Add a model progress callback interface.
- Teach `LoggingExecutor` or `ExecutorRegistry` to pass model progress callbacks to adapters.
- Implement streaming Ollama chat responses with `stream: true`.
- Accumulate streamed content into the same final `ModelResponse` shape used today.
- Count provider-reported token metrics from final Ollama response when available.
- Add approximate token counting fallback for live progress.
- Add unit tests with a fake streaming model adapter.
- Add an optional Ollama smoke run that demonstrates live progress events.
- Document how to tail `logs/execution.log` during long model runs.

## Dependencies

- Depends on the YAML CLI and live execution logs.
- Supports debugging task 010 local-model e2e runs.

## Done

During a slow Ollama run, `runs/<scenario_id>/<run_id>/logs/execution.log` receives periodic model progress events before the model task finishes.

## Implementation Notes

- Streaming support lives in `src/planfoldr/executors.py`.
- `OllamaModelAdapter` uses `stream: true` and accumulates streamed chunks into the existing `ModelResponse` shape.
- `ExecutorRegistry` exposes a model progress callback and annotates progress events with task id, attempt, model and provider.
- `LoggingExecutor` forwards model progress events into `logs/execution.log`.
- Stream chunks are written live under `trace/models/<execution_id>/chunks/`.
- The full chronological stream is written to `trace/models/<execution_id>/assembled.txt`.
- Parsed content and provider thinking text are split into `content.txt` and `thinking.txt`.
- The HTML report shows model text sections and includes cycle id in the task table.
- Mid-stream token counts use an approximate character-based counter; final stream metadata uses provider counts when Ollama reports them.
- Unit coverage for streaming progress lives in `tests/test_trace.py` with a fake streaming adapter.

## Line-by-Line Verification Audit

Audit source: `nl -ba quests/done/011_streaming_model_progress.md` before this section was appended; prior `Completion Audit` is summarized separately below.

- [x] Line 1: `# Task 011: Streaming Model Progress` checked and complete.
- [x] Line 2: blank separator preserved.
- [x] Line 3: `## Goal` checked and complete.
- [x] Line 4: blank separator preserved.
- [x] Line 5: `Add streaming model execution so long Ollama calls visibly make progress while they run.` checked and complete.
- [x] Line 6: blank separator preserved.
- [x] Line 7: `## Concept` checked and complete.
- [x] Line 8: blank separator preserved.
- [x] Line 9: `Current model execution uses a blocking Ollama request. During slow local-model runs, \`logs/execution.log\` only shows \`task_start\` an...` checked and complete.
- [x] Line 10: blank separator preserved.
- [x] Line 11: `## Necessary Conditions` checked and complete.
- [x] Line 12: blank separator preserved.
- [x] Line 13: `- Ollama adapter can use streaming API responses.` checked and complete.
- [x] Line 14: `- Model streaming progress is written to \`logs/execution.log\` while the task is still running.` checked and complete.
- [x] Line 15: `- Progress events include task id, attempt number and cumulative generated text length.` checked and complete.
- [x] Line 16: `- Progress events include token counts when the provider reports them.` checked and complete.
- [x] Line 17: `- If exact token counts are unavailable mid-stream, log an explicit approximate counter or \`unsupported\` marker.` checked and complete.
- [x] Line 18: `- Final model metadata captures streaming stats.` checked and complete.
- [x] Line 19: `- Timeouts still return a structured \`failure\` or \`retry_exceeded\` result.` checked and complete.
- [x] Line 20: `- Existing non-streaming tests remain deterministic.` checked and complete.
- [x] Line 21: blank separator preserved.
- [x] Line 22: `## Constraints` checked and complete.
- [x] Line 23: blank separator preserved.
- [x] Line 24: `- Do not require network or Ollama for regular unit tests.` checked and complete.
- [x] Line 25: `- Do not dump full model text into every progress log event.` checked and complete.
- [x] Line 26: `- Keep \`execution.log\` useful and compact.` checked and complete.
- [x] Line 27: `- Do not let streaming output drive links before output validation passes.` checked and complete.
- [x] Line 28: `- Preserve existing trace/report artifact layout.` checked and complete.
- [x] Line 29: blank separator preserved.
- [x] Line 30: `## Proposed Events` checked and complete.
- [x] Line 31: blank separator preserved.
- [x] Line 32: `Append JSONL events like:` checked and complete.
- [x] Line 33: blank separator preserved.
- [x] Line 34: `\`\`\`json` checked and complete.
- [x] Line 35: `{"event":"model_stream_start","task_id":"generate_project","attempt":1}` checked and complete.
- [x] Line 36: `{"event":"model_stream_progress","task_id":"generate_project","attempt":1,"chars":2048,"tokens":{"generated":256,"source":"approximate"}}` checked and complete.
- [x] Line 37: `{"event":"model_stream_finish","task_id":"generate_project","attempt":1,"chars":8192,"tokens":{"generated":1024,"source":"provider"}}` checked and complete.
- [x] Line 38: `\`\`\`` checked and complete.
- [x] Line 39: blank separator preserved.
- [x] Line 40: `## Subtasks` checked and complete.
- [x] Line 41: blank separator preserved.
- [x] Line 42: `- Add a model progress callback interface.` checked and complete.
- [x] Line 43: `- Teach \`LoggingExecutor\` or \`ExecutorRegistry\` to pass model progress callbacks to adapters.` checked and complete.
- [x] Line 44: `- Implement streaming Ollama chat responses with \`stream: true\`.` checked and complete.
- [x] Line 45: `- Accumulate streamed content into the same final \`ModelResponse\` shape used today.` checked and complete.
- [x] Line 46: `- Count provider-reported token metrics from final Ollama response when available.` checked and complete.
- [x] Line 47: `- Add approximate token counting fallback for live progress.` checked and complete.
- [x] Line 48: `- Add unit tests with a fake streaming model adapter.` checked and complete.
- [x] Line 49: `- Add an optional Ollama smoke run that demonstrates live progress events.` checked and complete.
- [x] Line 50: `- Document how to tail \`logs/execution.log\` during long model runs.` checked and complete.
- [x] Line 51: blank separator preserved.
- [x] Line 52: `## Dependencies` checked and complete.
- [x] Line 53: blank separator preserved.
- [x] Line 54: `- Depends on the YAML CLI and live execution logs.` checked and complete.
- [x] Line 55: `- Supports debugging task 010 local-model e2e runs.` checked and complete.
- [x] Line 56: blank separator preserved.
- [x] Line 57: `## Done` checked and complete.
- [x] Line 58: blank separator preserved.
- [x] Line 59: `During a slow Ollama run, \`runs/<scenario_id>/<run_id>/logs/execution.log\` receives periodic model progress events before the model tas...` checked and complete.
- [x] Line 60: blank separator preserved.
- [x] Line 61: `## Implementation Notes` checked and complete.
- [x] Line 62: blank separator preserved.
- [x] Line 63: `- Streaming support lives in \`src/planfoldr/executors.py\`.` checked and complete.
- [x] Line 64: `- \`OllamaModelAdapter\` uses \`stream: true\` and accumulates streamed chunks into the existing \`ModelResponse\` shape.` checked and complete.
- [x] Line 65: `- \`ExecutorRegistry\` exposes a model progress callback and annotates progress events with task id, attempt, model and provider.` checked and complete.
- [x] Line 66: `- \`LoggingExecutor\` forwards model progress events into \`logs/execution.log\`.` checked and complete.
- [x] Line 67: `- Stream chunks are written live under \`trace/models/<execution_id>/chunks/\`.` checked and complete.
- [x] Line 68: `- The full chronological stream is written to \`trace/models/<execution_id>/assembled.txt\`.` checked and complete.
- [x] Line 69: `- Parsed content and provider thinking text are split into \`content.txt\` and \`thinking.txt\`.` checked and complete.
- [x] Line 70: `- The HTML report shows model text sections and includes cycle id in the task table.` checked and complete.
- [x] Line 71: `- Mid-stream token counts use an approximate character-based counter; final stream metadata uses provider counts when Ollama reports them.` checked and complete.
- [x] Line 72: `- Unit coverage for streaming progress lives in \`tests/test_trace.py\` with a fake streaming adapter.` checked and complete.

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Goal, Concept, Necessary Conditions, Constraints, Proposed Events, Subtasks, Dependencies, Done and Implementation Notes line is complete.
- ✅ Evidence: streaming support in `src/planfoldr/executors.py`, live logging/report support in `src/planfoldr/trace.py` and fake streaming coverage in `tests/test_trace.py`.
- ✅ No unchecked quest lines remain in this file.
