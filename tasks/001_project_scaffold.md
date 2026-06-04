# Task 001: Project Scaffold

## Goal

Create the initial implementation scaffold for Phase 2.

## Concept

The repository needs enough structure for independent agents to add runtime pieces without fighting over one large file.

## Necessary Conditions

- A language/runtime choice is explicit in the repository.
- Source, tests, examples and generated run artifacts have clear directories.
- A basic test command exists.
- `.gitignore` excludes generated run artifacts and caches.
- Documentation points to the next task.

## Constraints

- Do not implement business logic here.
- Do not add network-only setup as a hard requirement.
- Keep files small and boring.

## Phase 2 Decisions

- Use Python.
- Package/module name is `planfoldr`.
- Dependencies are recorded in `requirements.txt`.
- Canonical test command is `python -m pytest` from a virtualenv.
- Generated run workdirs must not be committed; `runs/` remains ignored.

## Subtasks

- Create Python project metadata.
- Create package/project metadata.
- Create source directory.
- Create test directory.
- Add a minimal smoke test.
- Add or update `.gitignore`.
- Document local setup.

## Dependencies

- Depends on Phase 1 docs.
- Blocks task 002.

## Done

An agent can clone the repo, run the documented test command and see one passing smoke test.

## Implementation Notes

- Python package metadata lives in `pyproject.toml`.
- Runtime package source lives under `src/planfoldr/`.
- Tests live under `tests/`.
- Local setup and the canonical test command are documented in `README.md`.
- Continue with [Task 002: Schema And Loader](002_schema_and_loader.md).
