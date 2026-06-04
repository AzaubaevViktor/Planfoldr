You are executing a Planfoldr repair task.

The generated project's tests failed. Return only JSON with replacement files:

{
  "status": "success",
  "files": [
    {"path": "{{ inputs.repository_path }}/todo/__init__.py", "content": "..."}
  ]
}

Return every file that must be replaced to make the tests pass. The path above is only an example.

Use the traceback below as the source of truth. If imports fail, fix the package exports and module names. Do not create both a top-level `todo.py` file and a `todo/` package.

Latest `run_tests` stdout:

```text
{{ tasks.run_tests.output.stdout }}
```

Latest `run_tests` stderr:

```text
{{ tasks.run_tests.output.stderr }}
```

Keep all paths inside `{{ inputs.repository_path }}`. Do not decide workflow transitions.
