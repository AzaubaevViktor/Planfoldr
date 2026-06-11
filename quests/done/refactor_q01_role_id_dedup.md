# Task refactor_q01_role_id_dedup: Устранить дублирование `role_id` в tools_impl и cycle
File name: `refactor_q01_role_id_dedup.md`

## Статус

Текущий статус: active
Блокирован: нет
Описание: Два разных модуля повторяют одно и то же inline-выражение для получения идентификатора
роли. В `tools_impl.py` выражение `ctx.role.id if ctx.role else "*"` встречается 7 раз; в
`cycle.py` — `getattr(self.role, "id", <fallback>)` встречается 7 раз с тремя разными
fallback-значениями (`None`, `"verifier"`, `"model"`, `"executor"`). Дополнительно:
`handle_write_context` и `handle_update_context` содержат идентичную логику «создать секцию, если
нет → применить патч или записать → вернуть версию».

---

## Дублирующийся код

### 1. `ctx.role.id if ctx.role else "*"` — 7 мест в `tools_impl.py`

```python
# строки 230, 232, 236, 243, 256, 257, 259 — все содержат:
ctx.role.id if ctx.role else "*"
```

Все семь вызовов передают результат в `KnowledgeBase.read` или `KnowledgeBase.write`, которые
принимают `role: str`. При `ctx.role is None` корректное значение — `"*"` (wildcard, любая роль).

**Исправление**: добавить свойство-помощник `role_id` в `ToolContext`:

```python
@property
def role_id(self) -> str:
    return self.role.id if self.role is not None else "*"
```

Заменить все 7 вхождений на `ctx.role_id`.

### 2. `getattr(self.role, "id", <fallback>)` — 7 мест в `cycle.py`

```python
# строки 164, 238, 320, 496, 500, 504, 513
getattr(self.role, "id", None)       # строка 164
getattr(self.role, "id", "verifier") # строка 238
getattr(self.role, "id", "model")    # строка 320
getattr(self.role, "id", "executor") # строки 496, 500, 504, 513
```

`self.role` — `Any`, но в каждом месте это либо `Executor`, у которого всегда есть `.id`, либо
`None`. Единственный нужный fallback — `"executor"` (разумный дефолт; `"verifier"` и `"model"` —
слишком специфичные строки для единственного места использования и путают читателя).

**Исправление**: добавить свойство `_role_id` в `Cycle`:

```python
@property
def _role_id(self) -> str:
    return getattr(self.role, "id", "executor")
```

Заменить все 7 вхождений. Строка 164 (CYCLE_STARTED, поле `role`) исторически могла быть `None`
(нет роли в тестах) — использовать `self._role_id or None` только там, чтобы сохранить семантику
nullable в audit payload.

### 3. Дублирование `handle_write_context` / `handle_update_context` в `tools_impl.py`

`handle_update_context` (строки 247–260) полностью поглощается `handle_write_context` (225–237):
- оба создают секцию если её нет
- оба применяют `apply_unified_patch` при наличии `patch=`
- оба возвращают `{"section": section, "version": version}`

Разница только в том, что `handle_update_context` *требует* `patch=`, тогда как
`handle_write_context` принимает либо `content=`, либо `patch=`.

**Исправление**: удалить `handle_update_context` как отдельную функцию; добавить в
`handle_write_context` проверку «если есть `patch=`, а `content=` нет — обязательно секция должна
существовать», тем самым покрыв оба сценария. Обновить `DEFAULT_HANDLERS`: убрать отдельную
запись `"update_context"` и сделать так, чтобы `"update_context"` просто вызывал тот же хендлер
(алиас), либо удалить алиас и задокументировать, что `write_context` с `patch=` — правильный
путь.

---

## TODO

### RnD
1. Прочитать `src/planfoldr/tools_impl.py` полностью — убедиться, что `handle_update_context`
   не вызывается напрямую из других мест, кроме `DEFAULT_HANDLERS`.
   Verify: `grep -rn "handle_update_context\|update_context" src/ tests/`

2. Прочитать `src/planfoldr/cycle.py` полностью — убедиться, что все 7 getattr используют роль
   только как строковой идентификатор (не вызывают `.effective_prompt` или метод).
   Verify: вхождения найдены в audit-emit + ticket.transition + toolset.invoke; только строковые.

### Implementation
3. В `src/planfoldr/tools_impl.py` в класс `ToolContext` добавить свойство:
   ```python
   @property
   def role_id(self) -> str:
       return self.role.id if self.role is not None else "*"
   ```
   Заменить все 7 вхождений `ctx.role.id if ctx.role else "*"` на `ctx.role_id`.
   Verify: `grep -n "ctx\.role\.id if ctx\.role else" src/planfoldr/tools_impl.py` → 0 результатов.

4. В `src/planfoldr/tools_impl.py` удалить функцию `handle_update_context` (строки 247–260).
   В `handle_write_context` добавить: если `args.get("patch")` и не `target.exists()` (секции нет)
   — создать секцию перед применением патча (уже делается строкой 230/256). Убедиться, что
   `handle_write_context` корректно обрабатывает оба пути (patch= и content=).
   В `DEFAULT_HANDLERS` заменить запись `"update_context": ("base", handle_update_context)` на
   `"update_context": ("base", handle_write_context)` (алиас), чтобы не сломать существующие
   модели, которые могут звать `update_context` по имени.
   Verify: `grep -n "handle_update_context" src/planfoldr/tools_impl.py` → 0 результатов
   (кроме записи в DEFAULT_HANDLERS, которая заменена алиасом).

5. В `src/planfoldr/cycle.py` добавить свойство `_role_id` в класс `Cycle` (после `__init__`):
   ```python
   @property
   def _role_id(self) -> str:
       return getattr(self.role, "id", "executor")
   ```
   Заменить все 7 вхождений `getattr(self.role, "id", ...)` на `self._role_id`, кроме строки 164
   (поле `role` в CYCLE_STARTED) — там заменить на `self._role_id or None` (чтобы сохранить
   nullable семантику в audit-событии, которое тесты могут проверять на `None`).
   Verify: `grep -n "getattr(self\.role" src/planfoldr/cycle.py` → 0 результатов.

### Verification
6. Запустить полный тестовый набор:
   ```bash
   .venv/bin/python -m pytest -q
   ```
   Verify: все тесты зелёные, 0 новых FAILED/ERROR.

7. Проверить, что `update_context` алиас работает корректно — вызвать через toolset:
   ```bash
   .venv/bin/python -c "
   from planfoldr.tools_impl import DEFAULT_HANDLERS, handle_write_context
   assert DEFAULT_HANDLERS['update_context'][1] is handle_write_context, 'alias broken'
   print('alias ok')
   "
   ```
   Verify: вывод `alias ok`, нет исключений.

## Final Verification

- `.venv/bin/python -m pytest -q` — 0 FAILED, 0 ERROR.
- `grep -c "ctx\.role\.id if ctx\.role else" src/planfoldr/tools_impl.py` → `0`
- `grep -c "getattr(self\.role" src/planfoldr/cycle.py` → `0`
- `grep -c "handle_update_context" src/planfoldr/tools_impl.py` → `0` (только алиас в DEFAULT_HANDLERS, который теперь ссылается на handle_write_context).
