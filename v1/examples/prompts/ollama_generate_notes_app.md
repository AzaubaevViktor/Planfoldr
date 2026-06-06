You are executing a Planfoldr model task.

Create a small dependency-free Python notes knowledge-base project. Return only JSON.

The JSON must match this shape:

{
  "status": "success",
  "files": [
    {"path": "{{ inputs.repository_path }}/notes_app/__init__.py", "content": "..."}
  ]
}

Requirements:
- keep every path inside `{{ inputs.repository_path }}`;
- include multiple files;
- include a single Python package named `notes_app`;
- include `notes_app/__main__.py` so `python -m notes_app ...` works;
- include a CLI with these commands:
  - `add TITLE BODY --tags comma,separated,tags`
  - `list`
  - `list --tag TAG`
  - `search QUERY`
  - `export PATH`
  - `import PATH`
- persist notes as JSON using `NOTES_DB`, `NOTES_FILE`, or `NOTES_PATH` when one of those environment variables is set, otherwise use `notes.json` in the current working directory;
- note ids must be stable positive integers;
- note records must include title, body and tags;
- `search QUERY` must find text in title, body or tags;
- include generated tests that run with `python3 -m pytest`;
- include `AGENTS.md`;
- include `ARCHITECTURE.md`;
- use no external runtime dependencies;
- keep test imports consistent with the files you create;
- deliberately leave one repairable bug for the later repair task: `list --tag TAG` may match tags case-sensitively, so a later mixed-case regression test should fail before repair;
- do not include a generated test for mixed-case tag filtering;
- do not decide workflow transitions.
