from __future__ import annotations

from pathlib import Path

from ollama_speedtest.ollama_speedtest import (
    ModelInfo,
    OllamaError,
    build_prompt,
    load_state,
    parse_parameter_size_b,
    run_probe,
    save_state,
    select_models,
    should_skip_existing,
)


class FakeClient:
    def __init__(self, *, error: OllamaError | None = None) -> None:
        self.error = error
        self.calls = []

    def chat_stream(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return {
            "first_token_seconds": 0.12,
            "generation_tokens_per_second": 42.0,
            "generation_chars_per_second": 123.0,
            "prompt_eval_tokens_per_second": 100.0,
            "generated_tokens": 8,
            "generated_chars": 24,
            "prompt_tokens": 20,
            "wall_seconds": 0.5,
        }


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_build_prompt_prefers_root_md_files_before_src_py(tmp_path: Path) -> None:
    write(tmp_path / "B.md", "root b notes\n" * 20)
    write(tmp_path / "A.md", "root a notes\n" * 20)
    write(tmp_path / "src" / "planfoldr" / "z.py", "print('src py')\n" * 20)

    prompt = build_prompt(tmp_path, 2_000)

    a_index = prompt.index("A.md:")
    b_index = prompt.index("B.md:")
    py_index = prompt.index("src/planfoldr/z.py:")
    assert a_index < b_index < py_index
    assert "You are architector. You need to invent next steps for this project:" in prompt
    assert "```" in prompt


def test_build_prompt_variant_changes_sample_identity_and_content_choice(tmp_path: Path) -> None:
    write(tmp_path / "A.md", "alpha\n" * 200)
    write(tmp_path / "B.md", "bravo\n" * 200)
    write(tmp_path / "src" / "planfoldr" / "z.py", "print('src py')\n" * 200)

    first = build_prompt(tmp_path, 1_200, variant="model-a:1000:first")
    second = build_prompt(tmp_path, 1_200, variant="model-a:1000:second")

    assert "benchmark sample id." in first
    assert "benchmark sample id." in second
    assert first.splitlines()[0] != second.splitlines()[0]
    assert first != second


def test_run_probe_skips_when_known_context_window_is_too_small(tmp_path: Path) -> None:
    write(tmp_path / "AGENTS.md", "agent context\n" * 200)
    client = FakeClient()
    model = ModelInfo(name="tiny:latest", context_window=100)

    result = run_probe(client=client, model=model, root=tmp_path, size=2_500, num_predict=64)

    assert result.status == "skipped"
    assert "requires" in result.skipped_reason
    assert client.calls == []


def test_run_probe_turns_context_error_into_skipped_result(tmp_path: Path) -> None:
    write(tmp_path / "AGENTS.md", "agent context\n" * 100)
    client = FakeClient(error=OllamaError("prompt exceeds maximum context", context_related=True))
    model = ModelInfo(name="small:latest", context_window=None)

    result = run_probe(client=client, model=model, root=tmp_path, size=1_000, num_predict=64)

    assert result.status == "skipped"
    assert result.skipped_reason == "model reported insufficient context window"
    assert result.error == ""


def test_resume_logic_skips_terminal_entries_but_can_retry_errors() -> None:
    assert should_skip_existing({"status": "ok"}, rerun=False, retry_errors=False)
    assert should_skip_existing({"status": "skipped"}, rerun=False, retry_errors=False)
    assert should_skip_existing({"status": "error"}, rerun=False, retry_errors=False)
    assert not should_skip_existing({"status": "error"}, rerun=False, retry_errors=True)
    assert not should_skip_existing({"status": "running"}, rerun=False, retry_errors=False)
    assert not should_skip_existing({"status": "ok"}, rerun=True, retry_errors=False)


def test_model_selection_can_filter_under_ten_billion_parameters() -> None:
    models = [
        ModelInfo(name="small:latest", parameter_size="7B", parameter_count_b=parse_parameter_size_b("7B")),
        ModelInfo(name="large:latest", parameter_size="13B", parameter_count_b=parse_parameter_size_b("13B")),
        ModelInfo(name="unknown:latest", parameter_size="", parameter_count_b=None),
    ]

    selected = select_models(models, patterns=[], max_parameter_size_b=10.0)

    assert [model.name for model in selected] == ["small:latest"]


def test_state_jsonl_replays_latest_snapshot(tmp_path: Path) -> None:
    state_path = tmp_path / "state.jsonl"
    state = {"version": 1, "entries": {"small::100": {"model": "small", "size_chars": 100, "status": "running"}}}
    save_state(state_path, state, "small::100")
    state["entries"]["small::100"] = {"model": "small", "size_chars": 100, "status": "ok", "prompt_tokens": 25}
    save_state(state_path, state, "small::100")

    loaded = load_state(state_path)

    assert loaded["entries"]["small::100"]["status"] == "ok"
    assert loaded["entries"]["small::100"]["prompt_tokens"] == 25
    assert len(state_path.read_text(encoding="utf-8").splitlines()) == 2
