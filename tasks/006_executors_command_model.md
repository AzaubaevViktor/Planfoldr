# Task 006: Command And Model Executors

## Goal

Implement MVP executor types: `command` and `model`.

## Concept

Executors are adapters. They do work, but they do not decide workflow. The runtime wraps executor outputs into task result envelopes.

## Necessary Conditions

- Command executor can run configured commands.
- Command executor captures exit code, stdout and stderr.
- Model executor interface exists.
- Stub model adapter exists for tests.
- Ollama model adapter exists for local e2e.
- Model metadata is captured.
- Prompt id, hash, variables and rendered prompt are captured.

## Constraints

- Commands must go through permission checks.
- Model calls must go through budget checks.
- Do not make Ollama required for regular unit tests.

## Subtasks

- Implement executor registry.
- Implement command executor.
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
