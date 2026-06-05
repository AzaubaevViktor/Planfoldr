# Task 016: Ollama Model Size Policy

## Goal

Prevent demo and test runs from using Ollama models larger than 12B parameters.

## Concept

Large local models can be useful, but current development runs should stay within a predictable GPU budget. The runtime and docs need a clear policy: automated or recommended Ollama runs use models up to and including 12B only.

## Necessary Conditions

- Example commands use a <=12B model.
- Optional Ollama e2e tests default to a <=12B model.
- Docs state the <=12B rule.
- Any model comparison task respects the same limit.
- If a configured model appears larger than 12B, the developer receives a clear warning or failure.

## Constraints

- Do not block non-Ollama unit tests.
- Do not require network access for validation.
- Model-size detection may be conservative when a tag does not expose parameter count.

## Subtasks

- Pick the default <=12B model for local e2e.
- Update docs and task descriptions.
- Add a guard or helper for obvious model-size violations.
- Add tests for model-name validation where practical.

## Done

Project docs and optional Ollama commands consistently use models with 12B parameters or fewer.
