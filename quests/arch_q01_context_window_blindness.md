# Task arch_q01_context_window_blindness: Слепота к размеру контекстного окна — промпты неограниченного размера
File name: `arch_q01_context_window_blindness.md`

## Статус

Текущий статус: active
Блокирован: нет
Описание: Метод `Cycle._one_action()` отправляет системный + пользовательский промпт
произвольного размера в модель без каких-либо проверок. `ModelConfig.max_tokens_per_ticket`
существует как поле, но нигде не используется для ограничения длины промпта. По мере накопления
`changes_log`, evidence и KB-контента промпт может превысить контекстное окно модели — Ollama
молча усекает входящий контент, и модель начинает выдавать мусор или застревает в цикле.

---

## Конкретная дыра

### Место: `cycle.py`, метод `_one_action`

```python
def _one_action(self, phase: str, *, user: str, allowed: set) -> Action:
    system = f"..."
    messages = [{"role": "system", "content": system.strip()},
                {"role": "user", "content": user}]
    # ← нет проверки len(system) + len(user) против лимита модели
    response = self.model.generate(messages, progress=progress)
```

`user` собирается в `_changes_user()` и включает:
- `_contract_block()` — все команды верификации сценария
- `_checks_block()` — все команды тикета
- `self.local_memory["context"]` — все evidence, зависимости и related tickets
- `_progress_block()` — полный лог действий этого цикла
- `last_result` — результат последнего инструмента (может быть большим stdout/stderr)
- полный action reference

При 8 итерациях с large stdout каждой `bash`-команды суммарный промпт легко превышает 8–16k
токенов. Для Ollama-моделей с контекстом 8192 токена это **гарантированное усечение**.

### Место: `ModelConfig`

```python
max_tokens_per_ticket: int = 50_000  # объявлено, но нигде не читается
```

Поле объявлено в `ModelConfig.to_dict()`, но ни `Cycle`, ни `Orchestrator` его не используют.

---

## Что должно быть исправлено

### Часть A: Мягкое усечение промпта

Добавить в `Cycle._one_action()` оценку длины промпта в токенах (простая эвристика: `len(text)
// 4`) и усекать части с низким приоритетом, если сумма превышает порог:

Приоритет (от выброса к сохранению):
1. Выбросить: `changes_log` > 10 записей — оставить только 5 последних
2. Выбросить: `last_result` stdout/stderr > 1000 символов — обрезать до 500
3. Выбросить: `prior_evidence` в context > 5 записей — оставить последние 3
4. Сохранить: system, goal, contract, checks, action reference, last_result (обрезанный)

Порог усечения: `model_config.options.get("num_ctx", 8192) * 0.75` токенов (75% от контекстного
окна; остаток — на сгенерированный ответ).

### Часть B: Использовать `max_tokens_per_ticket` как hard cap

В `Orchestrator._run_cycle()` при делегировании бюджета учитывать `model_cfg.max_tokens_per_ticket`:

```python
ticket_budget = self.budget.delegate(
    {Metric.TOKENS: min(
        ticket.budget.get(Metric.TOKENS, DEFAULT_TICKET_BUDGET[Metric.TOKENS]),
        model_cfg.max_tokens_per_ticket
    )},
    scope="ticket", ticket_id=ticket.id
)
```

### Часть C: Логировать усечения в audit

Когда промпт усечён — эмитировать audit-событие `EventType.TOOL_INVOKED` с полем
`truncated=True` и `original_chars`, `truncated_chars`. Это позволит Visibility показывать
предупреждение о усечении в отчёте.

---

## TODO

### RnD
1. Прочитать `src/planfoldr/cycle.py` методы `_one_action`, `_changes_user`, `_progress_block`,
   `_contract_block`, `_checks_block` — замерить типичный размер промпта.
   Verify: добавить временный `print(len(user) // 4, "estimated tokens")` и запустить stub-тест,
   чтобы увидеть реальные цифры.

2. Прочитать `src/planfoldr/model.py` — убедиться, что `ModelConfig.options.get("num_ctx")` —
   правильное место для контекстного окна Ollama.
   Verify: `grep -n "num_ctx" src/planfoldr/scenario.py scenarios/` — посмотреть, как задаётся.

### Implementation
3. В `src/planfoldr/cycle.py` добавить метод `_truncate_prompt(user: str, system: str) -> str`,
   который:
   - вычисляет `estimated_tokens = (len(system) + len(user)) // 4`
   - вычисляет `ctx_limit = self.model_config.options.get("num_ctx", 8192)`
   - если `estimated_tokens > ctx_limit * 0.75`: обрезает `last_result` до 500 символов,
     оставляет только последние 5 записей `changes_log` в `_progress_block`,
     оставляет только последние 3 evidence в context
   - возвращает обновлённый `user`
   Вызывать перед `messages = [...]` в `_one_action`.
   Verify: unit-тест: создать Cycle с stub-моделью, вызвать `_one_action` с промптом > 75%
   лимита, убедиться что `len(user) // 4 < ctx_limit * 0.75` после усечения.

4. В `src/planfoldr/cycle.py` в метод `_one_action` добавить audit-событие при усечении:
   ```python
   if was_truncated:
       self.audit.emit(EventType.TOOL_INVOKED, ..., truncated=True,
                       original_chars=original_len, truncated_chars=len(user))
   ```
   Verify: stub-тест с большим промптом — в audit.jsonl должна быть запись с `truncated=true`.

5. В `src/planfoldr/orchestrator.py` в методе `_run_cycle` обернуть делегирование бюджета:
   ```python
   token_cap = min(
       ticket.budget.get(Metric.TOKENS, DEFAULT_TICKET_BUDGET[Metric.TOKENS]),
       model_cfg.max_tokens_per_ticket,
   )
   ticket_budget = self.budget.delegate({**ticket.budget, Metric.TOKENS: token_cap}, ...)
   ```
   Verify: создать тест с `ModelConfig(max_tokens_per_ticket=5000)` и тикетом с бюджетом
   `{tokens_used: 40000}` — убедиться, что делегированный бюджет ограничен 5000.

### Verification
6. Запустить полный тестовый набор:
   ```bash
   .venv/bin/python -m pytest -q
   ```
   Verify: все тесты зелёные.

7. Запустить e2e stub-тест с явным ограничением `num_ctx=512` в options модели и длинным
   промптом — убедиться, что цикл завершается без `Action(error=...)` из-за переполнения.
   Verify: результат цикла — `done` или `needs_review`, не `budget_exceeded`.

## Final Verification

- `.venv/bin/python -m pytest -q` → 0 FAILED
- В `src/planfoldr/cycle.py` нет кода, который отправляет промпт без проверки размера.
- `grep -n "max_tokens_per_ticket" src/planfoldr/orchestrator.py` → вхождение в `_run_cycle`.
- Stub-тест с `num_ctx=512` проходит без ошибок усечения.
