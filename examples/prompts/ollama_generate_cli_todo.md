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
- do not decide workflow transitions.
