from pathlib import Path

import pytest

from planfoldr.loader import LinkResolutionError, SchemaLoadError, load_scenario


FIXTURES = Path(__file__).parent / "fixtures" / "scenarios"
EXAMPLES = Path(__file__).parents[1] / "examples" / "scenarios"


def test_loads_fixture_scenario_with_linked_cycle_and_prompt() -> None:
    loaded = load_scenario(FIXTURES / "minimal_scenario.yaml")

    assert loaded.document.id == "minimal_scenario"
    assert loaded.cycles[0].document.id == "minimal_cycle"
    assert loaded.cycles[0].document.tasks[0].id == "plan"
    assert loaded.cycles[0].prompts["minimal_prompt"].content.startswith("# Minimal Prompt")


def test_loads_documented_example_scenario() -> None:
    loaded = load_scenario(EXAMPLES / "cli_todo_app.yaml")

    assert loaded.document.id == "cli_todo_app_demo"
    assert loaded.cycles[0].document.entrypoint == "plan_project"
    assert "plan_cli_todo_app" in loaded.cycles[0].prompts


def test_loads_complex_notes_ollama_example_scenario() -> None:
    loaded = load_scenario(EXAMPLES / "ollama_notes_app.yaml")

    assert loaded.document.id == "ollama_notes_app_demo"
    assert [cycle.document.id for cycle in loaded.cycles] == ["ollama_notes_plan", "ollama_notes_repair"]
    assert loaded.cycles[0].document.entrypoint == "plan_notes_project"
    assert loaded.cycles[1].document.entrypoint == "setup_workspace"
    assert "ollama_plan_notes_app" in loaded.cycles[0].prompts
    assert "ollama_generate_notes_app" in loaded.cycles[1].prompts
    assert "ollama_repair_notes_app" in loaded.cycles[1].prompts


def test_validation_error_names_file_yaml_path_expected_and_actual() -> None:
    with pytest.raises(SchemaLoadError) as exc_info:
        load_scenario(FIXTURES / "invalid_missing_goal.yaml")

    message = str(exc_info.value)
    assert "invalid_missing_goal.yaml" in message
    assert "$.goal" in message
    assert "required field" in message
    assert "<missing>" in message


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(SchemaLoadError) as exc_info:
        load_scenario(FIXTURES / "invalid_unknown_field.yaml")

    message = str(exc_info.value)
    assert "$.surprise" in message
    assert "no unknown field" in message
    assert "'unexpected_value'" in message


def test_missing_linked_cycle_fails_before_runtime() -> None:
    with pytest.raises(LinkResolutionError) as exc_info:
        load_scenario(FIXTURES / "missing_cycle_scenario.yaml")

    assert "Linked file does not exist" in str(exc_info.value)
