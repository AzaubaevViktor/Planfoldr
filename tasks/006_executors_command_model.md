# Task 006: Command, Tool And Model Executors

## Goal

Implement MVP executor types: `command`, `tool` and `model`.

## Concept

Executors are adapters. They do work, but they do not decide workflow. The runtime wraps executor outputs into task result envelopes.

## Necessary Conditions

- Command executor can run configured commands.
- Command executor captures exit code, stdout and stderr.
- Model executor interface exists.
- Tool executor interface exists for internal operations with explicit constraints.
- Stub model adapter exists for tests.
- Ollama model adapter exists for local e2e.
- Model metadata is captured.
- Prompt id, hash, variables and rendered prompt are captured.

## Constraints

- Commands must go through permission checks.
- Tool executors must go through permission checks.
- Model calls must go through budget checks.
- Do not make Ollama required for regular unit tests.

## Phase 2 Decisions

- Internal operations are separate tools with described constraints, not arbitrary shell snippets.
- Command executor boundary includes explicit `cwd`, controlled `env`, budget-derived timeout and filesystem checks before writes where possible.
- Model adapter input shape is `model`, `messages`, `config`, `tools`.
- Stub model chooses responses using all available fixture keys: task id, prompt id, fixture sequence and related metadata.
- If Ollama/local model is unavailable, return `failure` with a clear reason.

## Subtasks

- Implement executor registry.
- Implement command executor.
- Implement constrained tool executor interface.
- Implement model executor interface.
- Implement stub model adapter.
- Implement Ollama adapter.
- Implement prompt rendering and hashing.
- Add tests using the stub adapter.

## Dependencies

- Depends on tasks 003 and 005.
- Uses task 004 audit if available.
- Blocks tasks 007 and 010.

## Done

Stubbed model tasks and command tasks run through the same task execution path and produce traceable results.
