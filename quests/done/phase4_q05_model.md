# Task phase4_q05: Model adapter + runtime selection (level 5a)
File name: `phase4_q05_model.md`

## Status

Current status: done
Blocked by: phase4_q02 (Score)
Description: The replaceable executor + the model-agnostic action protocol.

## Goal

Implement ModelConfig/ModelResponse, an Ollama streaming adapter (reusing v1 token counting), a
deterministic StubModel, the JSON action parser, and a ModelRegistry that selects via the Score
System (never the model itself).

## Necessary Conditions

- `parse_action`: JSON-first (whole text, embedded object) with `<tool_call>` fallback; missing
  `action` → error.
- `OllamaModel.generate`: streams thinking/content, counts provider tokens (eval_count /
  prompt_eval_count), reports duration; emits progress for Visibility; degrades gracefully when
  Ollama is unavailable.
- `StubModel`: deterministic scripted/callable replies; counts approximate tokens.
- `ModelRegistry.select`: runtime selection via `ScoreSystem.best_model`; avoids a model flagged
  for switching after repeated fails. Model has no cross-call memory and no access to its score.

## Constraints

- The model does not manage budget (the cycle does), does not select itself, does not see other
  cycles' memory.

## Outcome

`planfoldr.model` importable; hermetic tests green; real Ollama path validated.

## Verification

- `.venv/bin/python -m pytest tests/test_model.py -q` → **8 passed, 1 skipped** (opt-in Ollama).
- Real model: `PLANFOLDR_OLLAMA_E2E=1 PLANFOLDR_MODEL=gemma4:26b-mlx pytest tests/test_model.py::test_ollama_real_token_count` → **1 passed in 12.35s**; gemma4:26b-mlx returned exact `{"action":"finish","args":{}}`, generated_tokens>0, duration_seconds>0.
- Concrete evidence:
  - `test_model.py::test_parse_action_embedded_in_prose` + `::test_parse_action_tool_call_fallback` — model-agnostic parsing.
  - `test_model.py::test_model_has_no_cross_call_memory` — isolation.
  - `test_model.py::test_registry_select_uses_score_system_not_the_model` — runtime selection + switch-avoidance.

## Implementation Notes

- Files: `src/planfoldr/model.py`, `tests/test_model.py`.
- `_extract_json_object` is a quote/escape-aware brace scanner so a model can wrap its JSON action
  in prose and still drive the cycle.
- The cycle (Q06) does the budget accounting: it reads `ModelResponse.total_tokens` +
  `duration_seconds` and charges the ticket budget, enforcing `max_tokens_per_ticket` via soft stop.
