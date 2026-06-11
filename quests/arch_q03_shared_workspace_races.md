# Task arch_q03_shared_workspace_races: Общий workspace = тихие гонки файлов между тикетами
File name: `arch_q03_shared_workspace_races.md`

## Статус

Текущий статус: active
Блокирован: нет
Описание: Все тикеты одного запуска работают в одном и том же `run_dir/workspace/`. Если два
тикета создают или редактируют один файл (напр. `main.py`, `requirements.txt`), второй
тикет молча перезапишет работу первого. Сейчас executor loop последовательный — гонки не
возникают. Но в архитектуре нет ни изоляции, ни лока, ни контракта, запрещающего параллелизм.
Любой шаг к параллельным циклам (несколько ролей одновременно) немедленно создаст хаос.

---

## Конкретная дыра

### `orchestrator.py` — единый workspace для всех

```python
# __init__, строка 123
self.workspace = self.run_dir / "workspace"
self.workspace.mkdir(parents=True, exist_ok=True)
```

```python
# _run_cycle, строка 375
cycle = Cycle(
    ...
    workspace=self.workspace,  # ← одинаковый для всех тикетов
    ...
)
```

### Пример конфликта

Тикет `developer-1`: создаёт `app/main.py` (100 строк, реализация v1).
Тикет `developer-2`: создаёт `app/main.py` (50 строк, реализация v2 с другим интерфейсом).

Второй тикет завершается успешно, первый становится `done`, но его работа уничтожена.
Ни audit-лог, ни report не показывают конфликт — оба тикета имеют evidence `file_edit
app/main.py [created]`.

### Связанная дыра: `_checks_already_satisfied` и гонки команд

```python
# orchestrator.py строка 340
results = [(i, c, run_command(c.spec, cwd=self.workspace, timeout=60)) for i, c in required]
```

Эта проверка запускает команды в общем workspace. Если `developer-1` создал `app.py`,
а `developer-2` ещё не запускался, `verify-1` найдёт файл и решит, что тикет выполнен.
Если потом `developer-2` перепишет `app.py`, `verify-1` уже отмечен `done` — ложная верификация.

---

## Что должно быть исправлено

### Часть A: Per-ticket рабочие директории

Каждый тикет получает поддиректорию внутри общего workspace:

```
run_dir/workspace/             ← общий read-only корень (shared fixtures, seed files)
run_dir/workspace/developer-1/ ← изолированный workspace тикета developer-1
run_dir/workspace/developer-2/ ← изолированный workspace тикета developer-2
```

В `Orchestrator._run_cycle()`:
```python
ticket_workspace = self.workspace / ticket.id
ticket_workspace.mkdir(parents=True, exist_ok=True)
cycle = Cycle(..., workspace=ticket_workspace, ...)
```

`allowed_paths` тоже обновлять: `[ticket_workspace.resolve(), self.workspace.resolve()]`
(общий корень читаем, но запись — только в ticket_workspace).

### Часть B: Сценарные accesses — копировать seed-файлы в ticket workspace

Если сценарий указывает `accesses: [{path: "fixtures/data.csv"}]`, файлы копируются из
`self.workspace` в `ticket_workspace` при создании тикета (shallow copy, только seed), а не
шарятся по ссылке. Это не нарушает изоляцию — каждый тикет получает свою копию.

### Часть C: safe_path — проверять именно ticket_workspace, не project workspace

В `tools_impl.safe_path()` логика уже проходит через `allowed_paths`. Часть A автоматически
исправляет это через обновление `allowed_paths`.

### Часть D: Документировать текущее ограничение

До реализации Части A — добавить явный комментарий в `orchestrator.py`:

```python
# NOTE: workspace is currently shared across all tickets. Per-ticket isolation (arch_q03) is
# pending. The executor loop is strictly sequential which prevents file races today, but
# do not introduce concurrent execution without implementing per-ticket workspaces first.
```

---

## TODO

### RnD
1. Прочитать `src/planfoldr/orchestrator.py` полностью — найти все места, где `self.workspace`
   передаётся в `Cycle` или в `run_command`. Убедиться, что нет других передач workspace.
   Verify: `grep -n "self\.workspace" src/planfoldr/orchestrator.py` — все вхождения понятны.

2. Прочитать `src/planfoldr/scenario.py` — понять, как `accesses` резолвятся в пути.
   Verify: `grep -n "accesses\|workspace" src/planfoldr/scenario.py src/planfoldr/orchestrator.py`.

3. Проверить тесты — убедиться, что `StubModel`-тесты не создают реальные файлы в workspace и
   не зависят от конкретного пути workspace.
   Verify: `grep -rn "workspace" tests/` → все тесты создают temp-директорию или используют
   `tmp_path` из pytest.

### Implementation
4. В `src/planfoldr/orchestrator.py` в методе `_run_cycle(ticket, queue_id, ...)`:
   - создать `ticket_workspace = self.workspace / ticket.id`
   - `ticket_workspace.mkdir(parents=True, exist_ok=True)`
   - обновить `allowed_paths = [ticket_workspace.resolve(), self.workspace.resolve()]`
   - передать `workspace=ticket_workspace` в `Cycle(...)` вместо `self.workspace`
   Verify: запустить `test_e2e_stub.py` — тест проходит, каждый тикет имеет свою поддиректорию.

5. В `src/planfoldr/orchestrator.py` в метод `_checks_already_satisfied(ticket)` — использовать
   `ticket_workspace = self.workspace / ticket.id` вместо `self.workspace`, если поддиректория
   существует; fallback на `self.workspace` если нет (для обратной совместимости).
   ```python
   ticket_ws = self.workspace / ticket.id
   cwd = ticket_ws if ticket_ws.exists() else self.workspace
   results = [(i, c, run_command(c.spec, cwd=cwd, timeout=60)) for i, c in required]
   ```
   Verify: stub-тест с двумя тикетами, каждый создаёт файл с одинаковым именем — оба
   помечаются `done`, оба файла существуют в своих поддиректориях.

6. В `src/planfoldr/orchestrator.py` в методе `_final_verification` — использовать `self.workspace`
   как cwd для верификационного тикета (итоговая верификация работает в корне, не в поддиректории).
   Verify: `grep -n "_final_verification" src/planfoldr/orchestrator.py` — убедиться, что
   `scenario-verify` тикет не получает `workspace/scenario-verify/` как cwd.

7. Добавить комментарий-предупреждение (Часть D) в `orchestrator.__init__` рядом с
   `self.workspace = self.run_dir / "workspace"`.
   Verify: `grep -n "Per-ticket isolation" src/planfoldr/orchestrator.py` → вхождение есть.

### Verification
8. Запустить полный тестовый набор:
   ```bash
   .venv/bin/python -m pytest -q
   ```
   Verify: 0 FAILED, 0 ERROR.

9. Написать тест `tests/test_workspace_isolation.py`:
   - Два тикета типа `code`, оба создают файл `output.txt` с разным содержимым.
   - Запустить через StubModel, обе скрипты `finish` сразу.
   - Проверить, что оба файла существуют в отдельных поддиректориях и не перезаписали друг друга.
   Verify: тест зелёный: `assert (ws / "developer-1" / "output.txt").read_text() != (ws / "developer-2" / "output.txt").read_text()`.

## Final Verification

- `.venv/bin/python -m pytest -q` → 0 FAILED.
- `grep -n "workspace=ticket_workspace" src/planfoldr/orchestrator.py` → вхождение в `_run_cycle`.
- Новый тест `tests/test_workspace_isolation.py` существует и зелёный.
- Предупреждающий комментарий `arch_q03` присутствует в `orchestrator.py`.
