# Task arch_q02_ollama_silent_failure: Тихое падение Ollama — недоступность модели маскируется под ошибку формата
File name: `arch_q02_ollama_silent_failure.md`

## Статус

Текущий статус: active
Блокирован: нет
Описание: `OllamaModel.generate()` возвращает `ModelResponse(available=False, content="")`
при сетевой ошибке (Connection refused, timeout и т.д.). Но `Cycle._one_action()` не проверяет
`response.available`. Пустой контент передаётся в `parse_action("")`, который возвращает
`Action(error="no action found")`. Это запускает счётчик `reformat_left=2`, тратя 2 итерации
на переформатирование несуществующего ответа, после чего цикл продолжает работу как будто ничего
не произошло. Нет audit-события о недоступности модели, нет retry с паузой, нет эскалации.

---

## Конкретная дыра

### Путь ошибки в `model.py` (строки 249–252)

```python
except (OSError, urllib.error.URLError) as exc:
    _emit(progress, "model_stream_error", reason=str(exc))
    return ModelResponse(content="", available=False, raw=str(exc),
                         metadata={"adapter": "ollama", "error": str(exc)})
```

`model_stream_error` эмитируется только через `stream_sink` (в terminal/WS), но **не через
`AuditLog`**. Событие не попадает в `audit.jsonl` и не будет видно в Visibility-отчёте.

### Путь вызова в `cycle.py` (строки 366–390)

```python
response = self.model.generate(messages, progress=progress)
# ← нет проверки response.available
# ...
return parse_action(response.content)  # ← parse_action("") → Action(error=...)
```

В `_action_loop` (строка 287):
```python
if action.error and reformat_left > 0:
    reformat_left -= 1
    last_result = {"protocol_error": action.error, "hint": "Reply with ..."}
    continue
```

При `reformat_left == 0` ошибка уже не обрабатывается: цикл просто идёт дальше. После 2
«protocol_error» от недоступной модели цикл исчерпывает `reformat_left` и продолжает итерации
как если бы модель молчала — до исчерпания `max_iterations`.

---

## Что должно быть исправлено

### Часть A: Проверять `response.available` в `_one_action`

Добавить проверку сразу после `response = self.model.generate(...)`:

```python
if not response.available:
    self.audit.emit(
        EventType.MODEL_STREAM,
        ticket_id=self.ticket.id, cycle_id=self.execution_id, phase=phase,
        model=self.model_config.id, available=False,
        error=response.raw or "model unavailable",
    )
    return Action(action="", error=f"model unavailable: {response.raw or 'connection error'}")
```

Этот Action с error будет обработан стандартным путём через `reformat_left`, но теперь в audit
будет видно, что это именно отказ модели, а не плохой формат.

### Часть B: Отличать «недоступна модель» от «неверный формат» в `_action_loop`

Ввести отдельный счётчик `model_fail_left = 1` (одна попытка retry при недоступности модели):

```python
if action.error and action.error.startswith("model unavailable"):
    if model_fail_left > 0:
        model_fail_left -= 1
        import time; time.sleep(2)  # короткая пауза перед retry
        last_result = {"error": action.error}
        continue
    # модель недоступна после retry — прерываем цикл, не тратим итерации впустую
    self.local_memory.setdefault("notes", []).append(
        f"stopped: model unavailable after retry in {phase}")
    return
```

### Часть C: Audit-событие для недоступности модели

В `EventType` (в `audit.py`) добавить тип `MODEL_UNAVAILABLE` (или переиспользовать
`MODEL_STREAM` с полем `available=False`). В Visibility это должно отображаться как
предупреждение «model offline» рядом с именем модели в State View.

### Часть D: Эмитировать ошибку модели через `AuditLog`, не только через `stream_sink`

В `OllamaModel.generate()` нет доступа к `AuditLog` — правильно не тащить его туда. Вместо этого
`_one_action` должен быть единственным местом, которое эмитирует audit-событие о недоступности
модели (Часть A достаточна).

---

## TODO

### RnD
1. Убедиться, что `response.available` — единственный флаг недоступности; проверить, не
   возвращает ли `OllamaModel` `content=""` в каких-то других случаях (e.g. пустой ответ модели).
   Verify: `grep -n "available" src/planfoldr/model.py` — единственное место присвоения `False`.

2. Проверить, что тест `test_e2e_stub.py` не использует `StubModel` с `available=False` —
   чтобы понимать, есть ли уже тест на этот путь.
   Verify: `grep -rn "available=False" tests/` → нет совпадений.

### Implementation
3. В `src/planfoldr/cycle.py`, метод `_one_action`, после строки `response = self.model.generate(...)`:
   ```python
   if not response.available:
       self.audit.emit(
           EventType.MODEL_STREAM,
           ticket_id=self.ticket.id, cycle_id=self.execution_id, phase=phase,
           model=self.model_config.id, content_chars=0, thinking_chars=0,
           tokens=0, available=False, error=response.raw or "model unavailable",
       )
       return Action(action="", error=f"model unavailable: {response.raw or 'connection error'}")
   ```
   Verify: unit-тест: создать `StubModel` с `available=False`-ответом (через патч или переопределение
   generate), запустить `_one_action` — получить `Action(error=..., action="")`.

4. В `src/planfoldr/cycle.py`, метод `_action_loop`, добавить ветку для `model unavailable`
   перед общей проверкой `action.error`:
   ```python
   model_fail_left = 1  # объявить до for-цикла
   # внутри цикла:
   if action.error and "model unavailable" in action.error:
       if model_fail_left > 0:
           model_fail_left -= 1
           import time; time.sleep(2)
           last_result = {"error": action.error, "hint": "retrying after model error"}
           continue
       self.local_memory.setdefault("notes", []).append(
           f"stopped: model unavailable after retry")
       return
   ```
   Verify: unit-тест: StubModel возвращает `ModelResponse(available=False)` дважды подряд →
   цикл завершается (return), не исчерпывая `max_iterations`.

5. Написать тест `tests/test_cycle_model_failure.py`:
   - `StubModel` с первым ответом `available=False`, вторым — корректный action `finish`
   - запустить `Cycle.run()` c `max_iterations=4`
   - проверить, что цикл завершился (не дошёл до 4 итераций из-за бесполезных retries)
   - проверить, что в audit-событиях есть `MODEL_STREAM` с `available=False`
   Verify: тест зелёный с `.venv/bin/python -m pytest tests/test_cycle_model_failure.py -v`.

### Verification
6. Запустить полный тестовый набор:
   ```bash
   .venv/bin/python -m pytest -q
   ```
   Verify: 0 FAILED, 0 ERROR.

7. Вручную убедиться, что в сценарии без Ollama (PLANFOLDR_OLLAMA_E2E не установлен) ни один
   тест не падает из-за изменений в `_one_action`.
   Verify: `.venv/bin/python -m pytest -q -m "not ollama"` → 0 FAILED.

## Final Verification

- `.venv/bin/python -m pytest -q` → 0 FAILED.
- `grep -n "response.available" src/planfoldr/cycle.py` → вхождение в `_one_action`.
- Новый тест `tests/test_cycle_model_failure.py` существует и зелёный.
- `grep -n "model unavailable" src/planfoldr/cycle.py` → вхождение в `_action_loop`.
