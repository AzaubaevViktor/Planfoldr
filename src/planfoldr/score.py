"""Score System (level 1).

Keeps result statistics for each model along three axes -- global, per-role and per-task-type
-- and exposes them so the **runtime** (never the model itself) can pick the best model for the
next cycle and switch models after repeated failures.

PHASE_3 "Баллы моделям" + PHASE_4 §16:
- base score = f(parameter_count): more params -> higher base, overridable by data.
- + : correct output, verified (command+model), budget saved, fast.
- - : failed (heavier penalty for *simpler* tasks), budget exhausted (heavy, by spent size),
      >80% token waste, false verification, over-engineering child tickets.
- after 2-3 same-type failures -> runtime takes another / more powerful model.
- the score system does NOT choose the model and the model never reads its own score.
- history is not reset when a provider changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from planfoldr.audit import AuditLog, EventType


SWITCH_THRESHOLD = 2  # consecutive same-task-type failures before runtime should switch


@dataclass
class ScoreWeights:
    correct_output: float = 1.0
    verified: float = 5.0
    budget_saved: float = 3.0       # multiplied by saved fraction [0,1]
    speed_bonus: float = 2.0        # multiplied by time-saved fraction [0,1]
    failed_base: float = -8.0       # scaled up for simpler tasks
    budget_exhausted: float = -10.0  # scaled by spent fraction over allocation
    token_waste: float = -3.0       # tokens_used > 80% of budget
    false_verification: float = -6.0
    over_engineering: float = -2.0  # per excess declined child ticket


@dataclass
class ModelScore:
    model_id: str
    base: float
    global_score: float
    by_role: Dict[str, float] = field(default_factory=dict)
    by_task_type: Dict[str, float] = field(default_factory=dict)
    consecutive_fails: Dict[str, int] = field(default_factory=dict)
    tickets: int = 0

    def role_score(self, role: str) -> float:
        return self.by_role.get(role, self.base)

    def task_score(self, task_type: str) -> float:
        return self.by_task_type.get(task_type, self.base)

    def to_dict(self) -> Dict[str, object]:
        return {
            "model_id": self.model_id,
            "base": self.base,
            "global_score": self.global_score,
            "by_role": dict(self.by_role),
            "by_task_type": dict(self.by_task_type),
            "consecutive_fails": dict(self.consecutive_fails),
            "tickets": self.tickets,
        }


def base_score_from_params(parameter_count: float) -> float:
    """More parameters -> higher base rank. parameter_count is the raw count; we score in
    billions so 26e9 -> 26.0 and 9e9 -> 9.0."""
    return float(parameter_count) / 1e9


class ScoreSystem:
    def __init__(self, audit: Optional[AuditLog] = None, weights: Optional[ScoreWeights] = None) -> None:
        self.audit = audit
        self.weights = weights or ScoreWeights()
        self.scores: Dict[str, ModelScore] = {}

    def register_model(self, model_id: str, parameter_count: float) -> ModelScore:
        if model_id not in self.scores:
            base = base_score_from_params(parameter_count)
            self.scores[model_id] = ModelScore(model_id=model_id, base=base, global_score=base)
        return self.scores[model_id]

    # -- recording ------------------------------------------------------------
    def record(
        self,
        model_id: str,
        *,
        role: str,
        task_type: str,
        passed: bool,
        verified: bool = False,
        difficulty: float = 0.5,
        tokens_used: float = 0.0,
        tokens_budget: float = 0.0,
        time_seconds: float = 0.0,
        time_budget_seconds: float = 0.0,
        budget_spent: float = 0.0,
        budget_allocated: float = 0.0,
        budget_exhausted: bool = False,
        false_verification: bool = False,
        declined_children: int = 0,
    ) -> float:
        score = self.scores.get(model_id) or self.register_model(model_id, 1e9)
        w = self.weights
        delta = 0.0
        reasons: List[str] = []

        if passed:
            delta += w.correct_output
            reasons.append("correct_output")
            if verified:
                delta += w.verified
                reasons.append("verified")
            if tokens_budget > 0 and tokens_used < tokens_budget:
                saved = max(0.0, 1.0 - tokens_used / tokens_budget)
                delta += w.budget_saved * saved
                reasons.append("budget_saved")
            if time_budget_seconds > 0 and time_seconds < time_budget_seconds:
                saved = max(0.0, 1.0 - time_seconds / time_budget_seconds)
                delta += w.speed_bonus * saved
                reasons.append("speed_bonus")
        else:
            # Simpler tasks (low difficulty) carry a heavier penalty.
            difficulty = min(max(difficulty, 0.05), 1.0)
            delta += w.failed_base * (2.0 - difficulty)
            reasons.append("failed")

        if budget_exhausted:
            over = 1.0
            if budget_allocated > 0:
                over = max(1.0, budget_spent / budget_allocated)
            delta += w.budget_exhausted * over
            reasons.append("budget_exhausted")
        if tokens_budget > 0 and tokens_used > 0.8 * tokens_budget:
            delta += w.token_waste
            reasons.append("token_waste")
        if false_verification:
            delta += w.false_verification
            reasons.append("false_verification")
        if declined_children > 0:
            delta += w.over_engineering * declined_children
            reasons.append("over_engineering")

        # Apply along all three axes.
        score.global_score += delta
        score.by_role[role] = score.role_score(role) + delta
        score.by_task_type[task_type] = score.task_score(task_type) + delta
        score.tickets += 1
        if passed:
            score.consecutive_fails[task_type] = 0
        else:
            score.consecutive_fails[task_type] = score.consecutive_fails.get(task_type, 0) + 1

        if self.audit is not None:
            self.audit.emit(
                EventType.MODEL_SCORE_UPDATED,
                model=model_id,
                role=role,
                task_type=task_type,
                delta=round(delta, 4),
                reasons=reasons,
                global_score=round(score.global_score, 4),
                role_score=round(score.by_role[role], 4),
                task_type_score=round(score.by_task_type[task_type], 4),
            )
        return delta

    # -- runtime helpers (NOT visible to the model) ---------------------------
    def should_switch(self, model_id: str, task_type: str, threshold: int = SWITCH_THRESHOLD) -> bool:
        score = self.scores.get(model_id)
        if score is None:
            return False
        return score.consecutive_fails.get(task_type, 0) >= threshold

    def combined(self, model_id: str, role: str, task_type: str) -> float:
        score = self.scores.get(model_id)
        if score is None:
            return 0.0
        return 0.5 * score.role_score(role) + 0.3 * score.task_score(task_type) + 0.2 * score.global_score

    def best_model(self, role: str, task_type: str, candidates: Iterable[str]) -> Optional[str]:
        """Runtime-side selection: highest combined score among candidates, preferring models
        not currently flagged for switching on this task type."""
        cands = list(candidates)
        if not cands:
            return None
        not_flagged = [c for c in cands if not self.should_switch(c, task_type)]
        pool = not_flagged or cands
        if self.audit is not None:
            ranked = sorted(pool, key=lambda c: self.combined(c, role, task_type), reverse=True)
            best = ranked[0]
            self.audit.emit(
                EventType.MODEL_SELECTED,
                model=best,
                role=role,
                task_type=task_type,
                ranking={c: round(self.combined(c, role, task_type), 4) for c in ranked},
            )
            return best
        return max(pool, key=lambda c: self.combined(c, role, task_type))

    def to_dict(self) -> Dict[str, object]:
        return {model_id: score.to_dict() for model_id, score in self.scores.items()}
