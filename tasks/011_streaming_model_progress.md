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
