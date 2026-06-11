# Task arch_q05_budget_delegation_overshoot: Делегирование бюджета не учитывает остаток родителя — тикеты стартуют на пустом проекте
File name: `arch_q05_budget_delegation_overshoot.md`

## Статус

Текущий статус: active
Блокирован: нет
Описание: `Budget.delegate()` создаёт дочерний бюджет с запрошенными лимитами, не проверяя,
сколько у родителя осталось. Если проект потратил 39 900 из 40 000 токенов, следующему тикету
всё равно делегируется `{tokens: 40_000}`. Дочерний бюджет не будет заблокирован до тех пор,
пока не истратит оставшиеся 100 токенов и родитель не выставит `exceeded=True`. Между делегацией
и достижением лимита тикет успевает начать цикл, отправить промпт, запустить команды — всё это
происходит хотя можно было сразу не запускать тикет.

---

## Конкретная дыра

### `budget.py` — делегирование без проверки остатка

```python
def delegate(self, limits: Mapping[str, float], *, scope: str, ticket_id=None) -> "Budget":
    child = Budget(limits, scope=scope, ticket_id=ticket_id, audit=self.audit, parent=self)
    # ← нет проверки self.remaining(metric) >= limits[metric]
    return child
```

### `orchestrator.py` — делегирование запускается перед циклом

```python
def _run_cycle(self, ticket, queue_id, ...):
    ticket_budget = self.budget.delegate(
        ticket.budget or dict(DEFAULT_TICKET_BUDGET),
        scope="ticket", ticket_id=ticket.id
    )
    # ← сразу после: Cycle(..., budget=ticket_budget).run()
```

Если `self.budget.blocked == True` здесь, то `_executor_loop` поймает это **только на следующей
итерации** (проверка `if self.budget.blocked: break` — в начале while). Текущая итерация уже
дошла до `_run_executor_cycle` и сейчас делегирует.

### Эффект «чемодан без ручки»

При `max_cycles=40` и `budget_exceeded` на 39-м цикле:
- `_executor_loop` получает следующий тикет (`_next_ready()`)
- вызывает `_run_executor_cycle(queue, ticket)` — **без проверки budget.blocked**
- там вызывается `_run_cycle` — делегирует бюджет, создаёт Cycle
- Cycle проверяет `self.budget.blocked` только **внутри** фаз — после первого вызова модели

Значит одна дополнительная модельная итерация гарантированно происходит после исчерпания
проектного бюджета.

---

## Что должно быть исправлено

### Часть A: Проверка остатка при делегировании

Добавить метод `Budget.remaining(metric)` и использовать его в `delegate()`:

```python
def remaining(self, metric: str) -> float:
    limit = self.limits.get(metric)
    if limit is None:
        return float("inf")
    return max(0.0, limit - self.usage.get(metric, 0.0))
```

В `delegate()` — если метрика задана в обоих лимитах (родитель и ребёнок), обрезать лимит
ребёнка до `min(requested, self.remaining(metric))`:

```python
def delegate(self, limits: Mapping[str, float], *, scope: str, ticket_id=None) -> "Budget":
    capped = {
        metric: min(float(val), self.remaining(metric))
        for metric, val in limits.items()
    }
    child = Budget(capped, scope=scope, ticket_id=ticket_id, audit=self.audit, parent=self)
    ...
```

### Часть B: Проверка `budget.blocked` перед запуском нового цикла в `_run_executor_cycle`

```python
def _run_executor_cycle(self, queue: Queue, ticket: Ticket) -> None:
    if self.budget.blocked:          # ← добавить guard
        return
    ...
```

Это дополнительная защита — даже если executor loop пропустил проверку.

### Часть C: Audit-событие «тикет пропущен из-за исчерпанного бюджета»

При срабатывании guard из Части B — эмитировать:
```python
self.audit.emit(EventType.BUDGET_EXCEEDED, scope="ticket",
                ticket_id=ticket.id, note="ticket skipped: project budget exhausted")
```

Это нужно для Visibility: Run Analysis должен показывать, сколько тикетов не стартовало из-за
бюджета, а не только сколько стартовало и потом прервалось.

### Часть D: Показывать `remaining` в `Budget.to_dict()`

```python
def to_dict(self) -> Dict[str, object]:
    return {
        ...,
        "remaining": {
            metric: self.remaining(metric)
            for metric in self.limits
        },
    }
```

Это позволяет Visibility показывать «осталось X токенов» в State View без вычислений на стороне
клиента.

---

## TODO

### RnD
1. Прочитать `src/planfoldr/budget.py` полностью — убедиться, что `delegate()` не имеет
   скрытой логики кроме создания `Budget(...)`.
   Verify: `delegate` — 8 строк, логики расчёта остатка нет.

2. Прочитать `src/planfoldr/orchestrator.py` методы `_executor_loop` и `_run_executor_cycle` —
   убедиться, что `budget.blocked` проверяется до `_run_executor_cycle`, но не внутри него.
   Verify: строка 269 (`if self.budget.blocked: break`) — только в `_executor_loop`, не в
   `_run_executor_cycle`.

3. Проверить тесты бюджета — убедиться, что нет теста, который полагается на то, что
   `delegate()` НЕ обрезает лимит.
   Verify: `grep -rn "delegate" tests/` — все вхождения понятны.

### Implementation
4. В `src/planfoldr/budget.py` добавить метод `remaining(metric: str) -> float`:
   ```python
   def remaining(self, metric: str) -> float:
       limit = self.limits.get(metric)
       if limit is None:
           return float("inf")
       return max(0.0, limit - self.usage.get(metric, 0.0))
   ```
   Verify: unit-тест: бюджет `{tokens: 1000}`, потрачено 600 → `remaining("tokens_used") == 400`.

5. В `src/planfoldr/budget.py` в методе `delegate()` заменить `Budget(limits, ...)` на
   `Budget(capped, ...)` где `capped` — обрезанные лимиты из Части A.
   Verify: unit-тест: родительский бюджет 200 токенов, уже потрачено 180, делегируем 1000 →
   дочерний лимит должен быть 20, не 1000. `assert child.limits["tokens_used"] == 20`.

6. В `src/planfoldr/orchestrator.py` в методе `_run_executor_cycle` добавить guard в начале:
   ```python
   if self.budget.blocked:
       self.audit.emit(EventType.BUDGET_EXCEEDED, scope="ticket",
                       ticket_id=ticket.id, note="ticket skipped: project budget exhausted")
       return
   ```
   Verify: stub-тест: запустить сценарий с очень маленьким проектным бюджетом (5000 токенов),
   проверить что audit.jsonl содержит `BUDGET_EXCEEDED` с полем `note` для пропущенных тикетов.

7. В `src/planfoldr/budget.py` в `to_dict()` добавить секцию `remaining`:
   ```python
   "remaining": {metric: self.remaining(metric) for metric in self.limits},
   ```
   Verify: `Budget({Metric.TOKENS: 1000}).to_dict()["remaining"]["tokens_used"] == 1000`.

### Verification
8. Запустить полный тестовый набор:
   ```bash
   .venv/bin/python -m pytest -q
   ```
   Verify: 0 FAILED, 0 ERROR.

9. Написать тест `tests/test_budget_delegation_cap.py`:
   - Создать `Budget({tokens_used: 200})`, потратить 180.
   - Вызвать `delegate({tokens_used: 1000})`.
   - Проверить, что `child.limits["tokens_used"] <= 20`.
   - Потратить 20 токенов через дочерний бюджет → `child.blocked == True`, `parent.blocked == True`.
   Verify: тест зелёный.

## Final Verification

- `.venv/bin/python -m pytest -q` → 0 FAILED.
- `grep -n "def remaining" src/planfoldr/budget.py` → вхождение метода.
- `grep -n "remaining" src/planfoldr/budget.py` → вхождение в `to_dict()` и `delegate()`.
- `grep -n "budget.blocked" src/planfoldr/orchestrator.py` → 2 вхождения: в `_executor_loop`
  и в `_run_executor_cycle`.
- Новый тест `tests/test_budget_delegation_cap.py` зелёный.
