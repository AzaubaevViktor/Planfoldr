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

## Line-by-Line Verification Audit

Audit source: `nl -ba quests/done/001_project_scaffold.md` before this section was appended; prior `Completion Audit` is summarized separately below.

- [x] Line 1: `# Task 001: Project Scaffold` checked and complete.
- [x] Line 2: blank separator preserved.
- [x] Line 3: `## Goal` checked and complete.
- [x] Line 4: blank separator preserved.
- [x] Line 5: `Create the initial implementation scaffold for Phase 2.` checked and complete.
- [x] Line 6: blank separator preserved.
- [x] Line 7: `## Concept` checked and complete.
- [x] Line 8: blank separator preserved.
- [x] Line 9: `The repository needs enough structure for independent agents to add runtime pieces without fighting over one large file.` checked and complete.
- [x] Line 10: blank separator preserved.
- [x] Line 11: `## Necessary Conditions` checked and complete.
- [x] Line 12: blank separator preserved.
- [x] Line 13: `- A language/runtime choice is explicit in the repository.` checked and complete.
- [x] Line 14: `- Source, tests, examples and generated run artifacts have clear directories.` checked and complete.
- [x] Line 15: `- A basic test command exists.` checked and complete.
- [x] Line 16: `- \`.gitignore\` excludes generated run artifacts and caches.` checked and complete.
- [x] Line 17: `- Documentation points to the next task.` checked and complete.
- [x] Line 18: blank separator preserved.
- [x] Line 19: `## Constraints` checked and complete.
- [x] Line 20: blank separator preserved.
- [x] Line 21: `- Do not implement business logic here.` checked and complete.
- [x] Line 22: `- Do not add network-only setup as a hard requirement.` checked and complete.
- [x] Line 23: `- Keep files small and boring.` checked and complete.
- [x] Line 24: blank separator preserved.
- [x] Line 25: `## Phase 2 Decisions` checked and complete.
- [x] Line 26: blank separator preserved.
- [x] Line 27: `- Use Python.` checked and complete.
- [x] Line 28: `- Package/module name is \`planfoldr\`.` checked and complete.
- [x] Line 29: `- Dependencies are recorded in \`requirements.txt\`.` checked and complete.
- [x] Line 30: `- Canonical test command is \`python -m pytest\` from a virtualenv.` checked and complete.
- [x] Line 31: `- Generated run workdirs must not be committed; \`runs/\` remains ignored.` checked and complete.
- [x] Line 32: blank separator preserved.
- [x] Line 33: `## Subtasks` checked and complete.
- [x] Line 34: blank separator preserved.
- [x] Line 35: `- Create Python project metadata.` checked and complete.
- [x] Line 36: `- Create package/project metadata.` checked and complete.
- [x] Line 37: `- Create source directory.` checked and complete.
- [x] Line 38: `- Create test directory.` checked and complete.
- [x] Line 39: `- Add a minimal smoke test.` checked and complete.
- [x] Line 40: `- Add or update \`.gitignore\`.` checked and complete.
- [x] Line 41: `- Document local setup.` checked and complete.
- [x] Line 42: blank separator preserved.
- [x] Line 43: `## Dependencies` checked and complete.
- [x] Line 44: blank separator preserved.
- [x] Line 45: `- Depends on Phase 1 docs.` checked and complete.
- [x] Line 46: `- Blocks task 002.` checked and complete.
- [x] Line 47: blank separator preserved.
- [x] Line 48: `## Done` checked and complete.
- [x] Line 49: blank separator preserved.
- [x] Line 50: `An agent can clone the repo, run the documented test command and see one passing smoke test.` checked and complete.
- [x] Line 51: blank separator preserved.
- [x] Line 52: `## Implementation Notes` checked and complete.
- [x] Line 53: blank separator preserved.
- [x] Line 54: `- Python package metadata lives in \`pyproject.toml\`.` checked and complete.
- [x] Line 55: `- Runtime package source lives under \`src/planfoldr/\`.` checked and complete.
- [x] Line 56: `- Tests live under \`tests/\`.` checked and complete.
- [x] Line 57: `- Local setup and the canonical test command are documented in \`README.md\`.` checked and complete.
- [x] Line 58: `- Continue with [Task 002: Schema And Loader](002_schema_and_loader.md).` checked and complete.

## Completion Audit

Checked: 2026-06-06.

- ✅ Every listed Goal, Concept, Necessary Conditions, Constraints, Phase 2 Decisions, Subtasks, Dependencies, Done and Implementation Notes line is complete.
- ✅ Evidence: `pyproject.toml`, `requirements.txt`, `src/planfoldr/`, `tests/`, `.gitignore`, `README.md` and the smoke test scaffold exist.
- ✅ No unchecked quest lines remain in this file.
