# Planfoldr

Deterministic multi-cycle pipeline builder.

Planfoldr builds agentic flows where the model is not the controller. The deterministic runtime controls scenarios, cycles, tasks, budgets, permissions, context updates, verification and trace reporting. Models are executors inside selected tasks.

## Phase 1 Status

Phase 1 is complete as a product and architecture discovery phase.

Primary decisions are captured in:
- [ARCHITECTURE.md](ARCHITECTURE.md) — target architecture and MVP boundaries.
- [docs/phase_1/PHASE_1_COMPLETE.md](docs/phase_1/PHASE_1_COMPLETE.md) — Phase 1 completion marker and Phase 2 entry point.
- [docs/phase_1/DECISIONS.md](docs/phase_1/DECISIONS.md) — normalized decisions from answered questions.
- [docs/phase_1/MVP_SPEC.md](docs/phase_1/MVP_SPEC.md) — MVP requirements and acceptance criteria.
- [docs/phase_1/SCHEMA_DRAFT.md](docs/phase_1/SCHEMA_DRAFT.md) — initial YAML and trace schema draft.
- [tasks](tasks) — implementation tasks for Phase 2.

The raw Phase 1 questionnaire remains in [QUESTIONS_PHASE_1.md](QUESTIONS_PHASE_1.md).

## Phase 2 Entry Point

Start Phase 2 from [tasks/001_project_scaffold.md](tasks/001_project_scaffold.md), then follow [docs/phase_1/IMPLEMENTATION_ORDER.md](docs/phase_1/IMPLEMENTATION_ORDER.md).
