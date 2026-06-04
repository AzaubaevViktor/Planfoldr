You are executing a Planfoldr model task.

Create a small Python CLI todo-list project. Return only JSON.

The JSON must match this shape:

{
  "status": "success",
  "files": [
    {"path": "{{ inputs.repository_path }}/todo/__init__.py", "content": "..."}
  ]
}

Requirements:
- include multiple files;
- include tests that run with `python3 -m pytest`;
- include AGENTS.md;
- include ARCHITECTURE.md;
- use no external runtime dependencies;
- keep paths inside `{{ inputs.repository_path }}`;
- use a single Python package directory named `todo`;
- do not create a top-level `todo.py` file;
- make `todo/__init__.py` export the public API used by tests;
- if tests import `Todo` or `TodoList` from `todo`, those names must exist in `todo/__init__.py`;
- keep test imports consistent with the files you create;
- do not decide workflow transitions.
