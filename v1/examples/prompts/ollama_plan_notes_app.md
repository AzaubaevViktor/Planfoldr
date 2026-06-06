You are executing a Planfoldr supervision task.

Create a short structured plan for building and repairing a small Python notes knowledge-base app. Return only JSON.

The JSON must match this shape:

{
  "status": "success",
  "plan": [
    {"id": "generate", "goal": "generate a dependency-free notes app", "evidence": "generated tests pass"},
    {"id": "regression", "goal": "prove a mixed-case tag regression fails", "evidence": "regression test fails before repair"},
    {"id": "repair", "goal": "repair the app without deleting tests", "evidence": "all tests pass and inventory is preserved"}
  ],
  "evidence_required": [
    "initial generated tests pass",
    "mixed-case tag regression fails before repair",
    "repair makes the full suite pass",
    "test inventory is preserved"
  ]
}

Keep the plan concrete and bounded. Do not decide workflow transitions.
