# Вопросы Phase 2

Вопросы для проработки во время имплементации MVP.

На эти вопросы нужно отвечать инкрементально по мере выполнения задач. Ответы должны обновлять соответствующий task-файл, draft схемы, архитектурный документ или код реализации.

## 1. Скелет проекта

### 1. Какой стек использовать для Phase 2?

- Ответ:
- Цель ответа: выбрать один стек и зафиксировать почему.
- Текущее предположение: Python, потому что в репозитории уже Python-ориентированный `.gitignore`, runtime завязан на CLI/тесты, а YAML/schema tooling простые.
- Влияет на: task 001.

### 2. Как должно называться package/module?

- Ответ:
- Цель ответа: выбрать стабильное import-name.
- Текущее предположение: `planfoldr`.
- Влияет на: task 001.

### 3. Какая команда тестов должна быть канонической?

- Ответ:
- Цель ответа: одна команда, которую будут использовать агенты и будущий CI.
- Текущее предположение: `python -m pytest`.
- Влияет на: task 001.

### 4. Какие generated-директории нельзя коммитить?

- Ответ:
- Цель ответа: точные записи для `.gitignore`.
- Текущее предположение: `runs/`, Python caches, test caches.
- Влияет на: task 001.

## 2. Schema и loader

### 5. На чем реализовать схемы: dataclasses, Pydantic или plain dictionaries?

- Ответ:
- Цель ответа: один подход к валидации scenario/cycle/task.
- Текущее предположение: Pydantic, если зависимость приемлема; dataclasses плюс явные validators, если хотим минимизировать зависимости.
- Влияет на: task 002.

### 6. Какой YAML parser использовать?

- Ответ:
- Цель ответа: выбрать dependency и ожидаемое поведение parser-а.
- Текущее предположение: PyYAML для MVP.
- Влияет на: task 002.

### 7. Как resolve-ить относительные пути?

- Ответ:
- Цель ответа: выбрать root-relative или file-relative правило.
- Текущее предположение: linked YAML и prompt-файлы resolve-ятся относительно файла, который на них ссылается.
- Влияет на: task 002.

### 8. Насколько строгими должны быть unknown fields?

- Ответ:
- Цель ответа: reject, warn или preserve.
- Текущее предположение: reject unknown fields в core contracts, preserve extension fields только под явными `metadata` или `x_` keys.
- Влияет на: task 002.

### 9. Как представлять ошибки schema validation?

- Ответ:
- Цель ответа: форма error object.
- Текущее предположение: file path, YAML path, expected field/type, preview фактического значения.
- Влияет на: task 002.

## 3. Runtime core

### 10. Какая точная форма result envelope?

- Ответ:
- Цель ответа: JSON-serializable структура, которую используют все executors.
- Текущее предположение: выровнять с `docs/phase_1/SCHEMA_DRAFT.md`.
- Влияет на: task 003.

### 11. Как cycle выбирает первую task?

- Ответ:
- Цель ответа: explicit `entrypoint` или вывод из порядка tasks.
- Текущее предположение: добавить explicit `entrypoint`, даже если Phase 1 не требовала его, потому что это убирает неоднозначность.
- Влияет на: task 003 и обновление схемы.

### 12. Как terminal states представлены в links?

- Ответ:
- Цель ответа: точные reserved values.
- Текущее предположение: `success`, `fail`, `parent`.
- Влияет на: task 003.

### 13. Outcome names должны быть `need_*` или `needs_*`?

- Ответ:
- Цель ответа: единая naming convention.
- Текущее предположение: оставить значения из Phase 1: `need_context`, `need_decision`, `need_answer`, `need_inner_cycle`, `need_permission`, `need_tool`.
- Влияет на: task 003.

### 14. Сколько parallelism реализовать в MVP?

- Ответ:
- Цель ответа: sequential, async cycles или thread-per-cycle.
- Текущее предположение: сначала реализовать детерминированное sequential execution; API cycle runner-а оставить async-ready. Реальную concurrency добавлять только когда тест потребует.
- Влияет на: task 003.

### 15. Как parent-child communication работает в коде?

- Ответ:
- Цель ответа: модель request/response.
- Текущее предположение: child возвращает typed outcome с `request` payload; parent link мапит его на task или terminal decision.
- Влияет на: task 003.

## 4. Context, state и audit

### 16. Какая форма хранения context?

- Ответ:
- Цель ответа: nested dict, typed object или event-derived snapshot.
- Текущее предположение: nested dict snapshots плюс immutable audit events в MVP.
- Влияет на: task 004.

### 17. Какие exact scope names использовать?

- Ответ:
- Цель ответа: канонические строки scope.
- Текущее предположение: `task`, `cycle`, `scenario`, `decision_log`, `audit_log`.
- Влияет на: task 004.

### 18. Как context permissions выражаются в YAML?

- Ответ:
- Цель ответа: схема `read`, `write`, `delete`.
- Текущее предположение: `context_access.read/write/delete` как arrays of dotted paths.
- Влияет на: task 004 и обновление схемы.

### 19. Что такое audit event?

- Ответ:
- Цель ответа: поля для event type, actor, scope, path, before/after или redacted values.
- Текущее предположение: event id, timestamp, actor id, action, scope path, value summary, result.
- Влияет на: task 004.

### 20. Какие facts автоматически поднимаются вверх?

- Ответ:
- Цель ответа: явное правило.
- Текущее предположение: никакие, кроме metadata результата task; все domain facts требуют explicit propagation.
- Влияет на: task 004.

## 5. Budgets и permissions

### 21. Как измеряется model budget?

- Ответ:
- Цель ответа: tokens, money-like units или abstract counter.
- Текущее предположение: abstract numeric budget в MVP, потому что локальная Ollama может не отдавать cost.
- Влияет на: task 005.

### 22. Как enforce-ить RAM budget?

- Ответ:
- Цель ответа: enforce, observe или placeholder.
- Текущее предположение: хранить configured budget и report unsupported enforcement в MVP, если process tooling не даст дешевый способ.
- Влияет на: task 005.

### 23. Как нормализовать filesystem allowlists?

- Ответ:
- Цель ответа: realpath behavior и root для relative paths.
- Текущее предположение: normalize относительно scenario file/root, сравнивать resolved absolute paths.
- Влияет на: task 005.

### 24. Как matching-ить command allowlist?

- Ответ:
- Цель ответа: binary only, full command или prefix.
- Текущее предположение: allowlist по binary/tool name, аргументы проверять отдельно только если task задает более строгие constraints.
- Влияет на: task 005.

### 25. Что происходит, когда nested cycle просит больше budget или permission?

- Ответ:
- Цель ответа: parent decision protocol.
- Текущее предположение: вернуть `budget_exceeded` или `need_permission` с report; parent link решает next task или fail.
- Влияет на: task 005.

## 6. Executors

### 26. Как представлять internal operations?

- Ответ:
- Цель ответа: file writes — это commands, special executors или runtime helpers?
- Текущее предположение: runtime helper executor для internal file materialization, а не arbitrary shell.
- Влияет на: task 006.

### 27. Где safety boundary command executor-а?

- Ответ:
- Цель ответа: cwd, env, timeout, filesystem access.
- Текущее предположение: explicit cwd, controlled env, timeout из budget, filesystem checks перед writes там, где возможно.
- Влияет на: task 006.

### 28. Какой interface у model adapter?

- Ответ:
- Цель ответа: сигнатура request/response метода.
- Текущее предположение: `generate(prompt, schema, model_config, context) -> ModelResponse`.
- Влияет на: task 006.

### 29. Как stub model выбирает response?

- Ответ:
- Цель ответа: по task id, prompt id, fixture sequence или всем вместе.
- Текущее предположение: fixture map по task id плюс optional sequence number.
- Влияет на: task 006 и 009.

### 30. Как Ollama adapter обрабатывает недоступную локальную модель?

- Ответ:
- Цель ответа: fail, skip или typed outcome.
- Текущее предположение: optional e2e test skips; runtime task возвращает `need_tool` или `failure` с понятной причиной.
- Влияет на: task 006 и 010.

## 7. Verification и validation

### 31. Какой schema dialect использовать для `input_schema` и `output_schema`?

- Ответ:
- Цель ответа: JSON Schema subset или custom schema.
- Текущее предположение: JSON Schema subset.
- Влияет на: task 007.

### 32. Нужен ли каждой task output field `status`?

- Ответ:
- Цель ответа: required или executor-derived.
- Текущее предположение: runtime result имеет outcome status; domain output задачи может иметь свои поля, но не обязан дублировать `status`, если scenario этого не хочет.
- Влияет на: task 007 и обновление схемы.

### 33. Как представлять verifier chains?

- Ответ:
- Цель ответа: `required_conditions` ссылается на verifier task ids или нужна отдельная list.
- Текущее предположение: `required_conditions[].verifier_task` ссылается на существующие verifier tasks.
- Влияет на: task 007.

### 34. Какие evidence должны производить verifier tasks?

- Ответ:
- Цель ответа: форма evidence.
- Текущее предположение: check id, status, command/model/script details, observed output, failure reason.
- Влияет на: task 007 и 008.

### 35. Как retries считаются в budgets?

- Ответ:
- Цель ответа: retry budget semantics.
- Текущее предположение: каждый retry потребляет model/tool call budgets.
- Влияет на: task 007.

## 8. Trace, replay и report

### 36. Куда писать trace files?

- Ответ:
- Цель ответа: правило path.
- Текущее предположение: scenario `outputs.trace_path`, default под `runs/<scenario_id>/trace.json`.
- Влияет на: task 008.

### 37. Какая версия trace schema?

- Ответ:
- Цель ответа: initial version string.
- Текущее предположение: `0.1`.
- Влияет на: task 008.

### 38. Что exactly означает task replay?

- Ответ:
- Цель ответа: replay mode semantics.
- Текущее предположение: восстановить task result из сохраненного trace без вызова model/tool; полезно для report/debug и downstream deterministic tests.
- Влияет на: task 008.

### 39. Что HTML report должен показывать первым?

- Ответ:
- Цель ответа: information architecture report-а.
- Текущее предположение: scenario summary, final status, cycle tree, task list, selected task details, model/tool panels, audit и budget summary.
- Влияет на: task 008.

### 40. Должен ли report embed-ить trace JSON?

- Ответ:
- Цель ответа: separate file или embedded data.
- Текущее предположение: static HTML embed-ит compact trace copy или ссылается на sibling `trace.json`; выбрать один вариант во время реализации.
- Влияет на: task 008.

## 9. E2E scenarios

### 41. Какие два stub e2e scenarios нужны?

- Ответ:
- Цель ответа: fixture names и expected final statuses.
- Текущее предположение: `cli_todo_success_stub` и `cli_todo_failure_stub`.
- Влияет на: task 009.

### 42. Какую failure должен демонстрировать unsuccessful scenario?

- Ответ:
- Цель ответа: один failure mode.
- Текущее предположение: invalid model output с последующим retry exhaustion, потому что это доказывает validation и retry behavior.
- Влияет на: task 009.

### 43. Насколько маленьким должен быть generated CLI todo project?

- Ответ:
- Цель ответа: expected file list.
- Текущее предположение: один source file, один test file, минимальный package metadata при необходимости.
- Влияет на: task 010.

### 44. На каком языке должен быть generated demo project?

- Ответ:
- Цель ответа: один язык для Ollama demo.
- Текущее предположение: Python, потому что tests могут запускаться тем же toolchain.
- Влияет на: task 010.

### 45. Что делать, если generated tests fail?

- Ответ:
- Цель ответа: fail immediately или ask model for patch.
- Текущее предположение: для первого MVP fail with rich report; patch loop может быть отдельным будущим scenario.
- Влияет на: task 010.

## 10. Documentation и handoff для агентов

### 46. Какие task files обновлять после implementation discoveries?

- Ответ:
- Цель ответа: правило update.
- Текущее предположение: обновлять active task file и downstream task, если они зависят от изменившихся assumptions.
- Влияет на: all tasks.

### 47. Как агентам фиксировать отклонения от Phase 1?

- Ответ:
- Цель ответа: одно место для записи.
- Текущее предположение: добавить секцию `Decision Updates` в relevant task file и обновить `docs/phase_1/DECISIONS.md`, если изменение core-level.
- Влияет на: all tasks.

### 48. Что коммитить после каждой task?

- Ответ:
- Цель ответа: commit boundary.
- Текущее предположение: одна task — один или несколько focused commits, все с prefix `[AI]`.
- Влияет на: all tasks.

### 49. Какой minimum evidence нужен перед тем, как считать task done?

- Ответ:
- Цель ответа: tests/docs/artifacts per task.
- Текущее предположение: passing relevant tests плюс обновленные docs/examples, если task изменила contracts.
- Влияет на: all tasks.

### 50. Что Phase 2 пока не должна решать?

- Ответ:
- Цель ответа: избежать scope creep.
- Текущее предположение: не решать production UI, distributed execution, full sandboxing, automatic model routing и full scenario replay до того, как MVP докажет runtime.
- Влияет на: all tasks.
