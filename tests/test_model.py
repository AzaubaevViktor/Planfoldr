import os

import pytest

from planfoldr.audit import AuditLog
from planfoldr.model import (
    ModelConfig,
    ModelRegistry,
    ModelResponse,
    OllamaModel,
    StubModel,
    parse_action,
)
from planfoldr.score import ScoreSystem


def test_parse_action_whole_json():
    a = parse_action('{"thinking": "writing the file", "action": "file_edit", "args": {"path": "x.py", "content": "print(1)"}}')
    assert a.action == "file_edit" and a.args["path"] == "x.py" and a.error is None
    assert "writing" in a.thinking


def test_parse_action_embedded_in_prose():
    text = 'Sure, here is my action:\n{"action": "bash", "args": {"cmd": "pytest"}}\nThanks!'
    a = parse_action(text)
    assert a.action == "bash" and a.args["cmd"] == "pytest"


def test_parse_action_tool_call_fallback():
    a = parse_action('<tool_call>{"name": "create_ticket", "arguments": {"title": "t"}}</tool_call>')
    assert a.action == "create_ticket" and a.args["title"] == "t"


def test_parse_action_missing_action_is_error():
    a = parse_action('{"foo": "bar"}')
    assert a.action == "" and a.error is not None


def test_stub_model_is_deterministic_and_counts_tokens():
    stub = StubModel(['{"action": "finish", "args": {}}'])
    r = stub.generate([{"role": "user", "content": "go"}])
    assert isinstance(r, ModelResponse)
    assert parse_action(r.content).action == "finish"
    assert r.generated_tokens > 0 and r.total_tokens >= r.generated_tokens


def test_stub_model_script_advances_in_order():
    stub = StubModel([{"action": "file_edit", "args": {}}, {"action": "finish", "args": {}}])
    first = parse_action(stub.generate([]).content).action
    second = parse_action(stub.generate([]).content).action
    assert (first, second) == ("file_edit", "finish")


def test_model_has_no_cross_call_memory():
    stub = StubModel(lambda messages: '{"action": "echo", "args": {"n": %d}}' % len(messages))
    r1 = stub.generate([{"role": "user", "content": "a"}])
    r2 = stub.generate([{"role": "user", "content": "a"}, {"role": "user", "content": "b"}])
    # Each call only sees the messages it was handed -- no shared/hidden state.
    assert parse_action(r1.content).args["n"] == 1
    assert parse_action(r2.content).args["n"] == 2


def test_registry_select_uses_score_system_not_the_model():
    audit = AuditLog()
    score = ScoreSystem(audit=audit)
    reg = ModelRegistry()
    reg.register(ModelConfig("big", provider="stub", parameter_count=26e9), StubModel("{}"))
    reg.register(ModelConfig("small", provider="stub", parameter_count=9e9), StubModel("{}"))
    chosen = reg.select("developer", "code", score)
    assert chosen.id == "big"  # higher base score wins
    # After repeated failures the runtime avoids the flagged model.
    score.record("big", role="developer", task_type="code", passed=False)
    score.record("big", role="developer", task_type="code", passed=False)
    assert reg.select("developer", "code", score).id == "small"


@pytest.mark.ollama
@pytest.mark.skipif(os.environ.get("PLANFOLDR_OLLAMA_E2E") != "1", reason="opt-in Ollama run")
def test_ollama_real_token_count():
    model = os.environ.get("PLANFOLDR_MODEL", "gemma4:26b-mlx")
    r = OllamaModel(model).generate(
        [{"role": "user", "content": 'Reply with exactly this JSON: {"action":"finish","args":{}}'}],
        fmt="json",
    )
    assert r.available, f"Ollama unavailable: {r.metadata}"
    assert r.generated_tokens > 0 and r.duration_seconds > 0
    assert parse_action(r.content).action == "finish"
