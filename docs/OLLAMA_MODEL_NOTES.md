# Ollama Model Notes

## Raw Response

`raw_response` in Ollama model traces is provider diagnostics, not the best human-readable model text.

For streaming Ollama calls it contains newline-delimited JSON payloads from `/api/chat`. Each line is one provider chunk with fields such as `model`, `message`, `done`, timestamps and final token counters. The generated answer is assembled separately from `message.content`; thinking text, when provided by the model, is assembled separately from `message.thinking`.

Use these files for inspection instead:

- `trace/models/<execution_id>/content.txt` - generated model content.
- `trace/models/<execution_id>/thinking.txt` - streamed thinking text when the provider emits it.
- `trace/models/<execution_id>/assembled.txt` - thinking plus content in stream order.
- `trace/models/<execution_id>/stream.jsonl` - compact chronological chunk events.

The HTML report summarizes Ollama JSONL `raw_response` instead of inlining it. The raw value remains in model metadata JSON for low-level provider debugging.

## Local <=12B Models Observed

On 2026-06-05, `ollama list` showed these installed <=12B candidates:

- `carstenuhlig/omnicoder-9b:latest`
- `hf.co/Tesslate/OmniCoder-9B-GGUF:Q4_K_M`
- `hf.co/Jackrong/Qwopus3.5-9B-Coder-GGUF:Q4_K_M`
- `batiai/qwen3.5-9b:q6`
- `gemma3:12b`

Larger installed models such as `qwen3-coder:30b` are outside the current demo policy and should not be used for routine Planfoldr test/demo runs.

Inspect the current local policy decision table with:

```bash
python -m planfoldr ollama-models
```

Run the same demo scenario across eligible installed models with:

```bash
python -m planfoldr compare-ollama-models examples/scenarios/ollama_cli_todo_app.yaml --ollama-timeout 180
```

The comparison command writes `model_comparison.json` and `model_comparison.html` under `runs/<scenario_id>/<comparison_id>/`. Each row links to the normal per-run `report.html` and `trace/report_data.json` for that model.

## Demo Result

Command run:

```bash
PLANFOLDR_RUN_OLLAMA_E2E=1 \
PLANFOLDR_OLLAMA_MODEL=carstenuhlig/omnicoder-9b:latest \
PLANFOLDR_OLLAMA_TIMEOUT=180 \
python -m pytest tests/test_ollama_e2e.py -vv -s
```

Result: the model generated valid JSON and files, but the full demo failed after repeated repair attempts exhausted `max_model_calls` (`6`). The failure mode was repeated `run_tests` exit code `5`, followed by budget exhaustion.

Current recommendation: use `carstenuhlig/omnicoder-9b:latest` as the default <=12B coding model for local smoke/debug runs because it streams correctly and produces parseable task JSON. Treat full e2e success as prompt/runtime work still in progress, not as guaranteed model behavior.
