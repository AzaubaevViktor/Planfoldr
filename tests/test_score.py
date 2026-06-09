from planfoldr.audit import AuditLog, EventType
from planfoldr.score import ScoreSystem, base_score_from_params


def test_base_score_grows_with_parameter_count():
    assert base_score_from_params(26e9) > base_score_from_params(9e9)
    s = ScoreSystem()
    s.register_model("gemma4:26b-mlx", 26e9)
    assert s.scores["gemma4:26b-mlx"].global_score == 26.0


def test_positive_criteria_increase_score_and_emit_event():
    audit = AuditLog()
    s = ScoreSystem(audit=audit)
    s.register_model("m", 10e9)
    before = s.scores["m"].global_score
    delta = s.record(
        "m", role="developer", task_type="code", passed=True, verified=True,
        tokens_used=2000, tokens_budget=10000, time_seconds=10, time_budget_seconds=60,
    )
    assert delta > 0 and s.scores["m"].global_score > before
    ev = [e for e in audit.events() if e.event_type == EventType.MODEL_SCORE_UPDATED][-1]
    assert "verified" in ev.payload["reasons"] and "budget_saved" in ev.payload["reasons"]
    # role + task_type axes updated, not just global.
    assert s.scores["m"].by_role["developer"] > before
    assert s.scores["m"].by_task_type["code"] > before


def test_simpler_failed_task_penalized_more_than_harder_one():
    s = ScoreSystem()
    s.register_model("easy", 10e9)
    s.register_model("hard", 10e9)
    d_easy = s.record("easy", role="developer", task_type="code", passed=False, difficulty=0.1)
    d_hard = s.record("hard", role="developer", task_type="code", passed=False, difficulty=0.9)
    assert d_easy < d_hard < 0  # simpler failure is the heavier penalty


def test_negative_criteria_each_subtract():
    s = ScoreSystem(audit=AuditLog())
    s.register_model("m", 10e9)
    waste = s.record("m", role="r", task_type="t", passed=True, tokens_used=9000, tokens_budget=10000)
    # token waste (>80%) drags an otherwise-correct ticket toward/under zero net of bonuses
    assert "token_waste" in _last_reasons(s, "m")
    s.record("m", role="r", task_type="t", passed=False, budget_exhausted=True,
             budget_spent=200, budget_allocated=100)
    assert "budget_exhausted" in _last_reasons(s, "m")
    s.record("m", role="r", task_type="t", passed=True, false_verification=True)
    assert "false_verification" in _last_reasons(s, "m")
    s.record("m", role="r", task_type="t", passed=True, declined_children=3)
    assert "over_engineering" in _last_reasons(s, "m")


def test_switch_signal_after_consecutive_failures():
    s = ScoreSystem()
    s.register_model("m", 10e9)
    s.record("m", role="developer", task_type="code", passed=False, difficulty=0.5)
    assert s.should_switch("m", "code") is False
    s.record("m", role="developer", task_type="code", passed=False, difficulty=0.5)
    assert s.should_switch("m", "code") is True  # 2-3 fails -> runtime switches
    # A success resets the streak.
    s.record("m", role="developer", task_type="code", passed=True)
    assert s.should_switch("m", "code") is False


def test_runtime_selects_best_and_avoids_flagged_model():
    audit = AuditLog()
    s = ScoreSystem(audit=audit)
    s.register_model("big", 26e9)
    s.register_model("small", 9e9)
    # By base score big wins for a fresh role/task.
    assert s.best_model("developer", "code", ["big", "small"]) == "big"
    # Flag "big" out via repeated failures -> runtime avoids it.
    s.record("big", role="developer", task_type="code", passed=False)
    s.record("big", role="developer", task_type="code", passed=False)
    assert s.best_model("developer", "code", ["big", "small"]) == "small"
    assert any(e.event_type == EventType.MODEL_SELECTED for e in audit.events())


def test_history_survives_provider_change_simulation():
    s = ScoreSystem()
    s.register_model("m", 10e9)
    s.record("m", role="r", task_type="t", passed=True)
    snapshot = s.scores["m"].global_score
    # "Provider change" = re-register same id; history (ticket count, score) must persist.
    s.register_model("m", 10e9)
    assert s.scores["m"].global_score == snapshot
    assert s.scores["m"].tickets == 1


def _last_reasons(s, model_id):
    return s.audit.events()[-1].payload["reasons"] if s.audit else []
