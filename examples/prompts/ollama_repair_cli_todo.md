You are executing a Planfoldr repair task.

The generated project's tests failed. Return only JSON with replacement files:

{
  "status": "success",
  "files": [
    {"path": "{{ inputs.repository_path }}/todo/cli.py", "content": "..."}
  ]
}

Keep all paths inside `{{ inputs.repository_path }}`. Do not decide workflow transitions.
