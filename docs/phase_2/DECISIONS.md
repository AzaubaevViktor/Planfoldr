# Решения Phase 2

Нормализованные ответы из `docs/phase_2/QUESTIONS.md`. Этот документ фиксирует решения для имплементации MVP.

## 1. Скелет проекта

- Стек: Python.
- Package/module name: `planfoldr`.
- Зависимости: `requirements.txt`.
- Каноническая команда тестов: `python -m pytest` из virtualenv.
- Generated run workdirs не коммитятся; основной путь для них — `runs/`.

## 2. Schema и loader

- Схемы реализуются на Pydantic.
- YAML parser: PyYAML.
- Относительные imports/links resolve-ятся относительно файла, который содержит ссылку.
- Unknown fields reject-ятся; все должно быть явно описано.
- Ошибка schema validation содержит file path, YAML path, expected field/type и preview фактического значения.

## 3. Runtime core

- Result envelope — JSON-serializable структура.
- Cycle выбирает первую task через explicit `entrypoint`.
- Terminal states в links: `success` и `fail`.
- `parent` не является terminal state; это control target для передачи решения наверх.
- Outcome naming использует `need_*`, не `needs_*`.
- MVP runtime выполняется sequential.
- Parent-child communication: child возвращает typed outcome с `request` payload, parent link решает следующий шаг.

## 4. Context, state и audit

- Context хранится как nested dict snapshots плюс immutable audit events.
- Scope names: `task`, `cycle`, `scenario`, `decision_log`, `audit_log`.
- Context permissions в YAML: `context_access.read/write/delete` как arrays of dotted paths.
- Audit event содержит event id, timestamp, actor id, action, scope path, value summary и result.
- Facts не поднимаются вверх автоматически как произвольные данные: нижний cycle сообщает результат верхнему cycle по заранее специфицированному формату.

## 5. Budgets и permissions

- Model budget может измеряться количеством запросов, токенами или cost, который возвращает provider.
- RAM budget в MVP не enforce-ится; можно хранить и репортить как unsupported/placeholder.
- Filesystem allowlists нормализуются через resolved paths. В будущем нужно предусмотреть jail-mount.
- Command permissions используют allowlist и blacklist по regex.
- Если nested cycle просит больше budget или permission, parent link решает следующий шаг.

## 6. Executors

- Internal operations представлены отдельными tools с описанными ограничениями.
- Command executor boundary: explicit `cwd`, controlled `env`, timeout из budget, filesystem checks перед writes где возможно.
- Model adapter interface: `model`, `messages`, `config`, `tools`.
- Stub model выбирает response по совокупности ключей: task id, prompt id, fixture sequence и другие доступные признаки.
- Если Ollama/local model недоступна, runtime возвращает `failure` с причиной.

## 7. Verification и validation

- `input_schema` и `output_schema` используют JSON Schema.
- Каждая task output должна иметь field `status`.
- Verifier — отдельная task, в том числе task типа `model`, внутри которой выполняется верификация. Можно сделать verifier template.
- Verifier evidence содержит status, доказательство и ссылку на audit log.
- Каждый retry учитывается в budgets.

## 8. Trace, replay и report

- Trace пишется в развесистую структуру папок, а не только в один плоский файл.
- Версия trace schema начинается с `0.1`.
- Task replay означает восстановление task result из сохраненного trace без вызова model/tool.
- HTML report сначала показывает структуру cycles/tasks и execution log с фильтрацией по cycles/tasks.
- Report должен позволять смотреть, что происходило в конкретном cycle/task/link/tool.
- Static HTML подгружает данные лениво из развесистой trace-структуры.

## 9. E2E scenarios

- Stub e2e должен покрывать success scenario и несколько bad scenarios.
- Bad scenarios должны быть на каждый важный элемент: budget exhaustion, retry exhaustion, разные failure-точки.
- Generated CLI todo project должен быть не совсем игрушечным: несколько файлов, без внешних зависимостей, плюс `AGENTS.md` и `ARCHITECTURE.md` внутри generated repo.
- Demo project language: Python.
- Если generated tests fail, runtime несколько раз прогоняет цикл исправления. Stub tests тоже должны покрывать этот loop.

## 10. Documentation и handoff

- После implementation discoveries обновляются active task file и downstream tasks, если они зависят от изменившихся assumptions.
- Отклонения от Phase 1 фиксируются в `Decision Updates` relevant task file и в core docs, если изменение core-level.
- После каждой task делается один или несколько focused commits с prefix `[AI]`.
- Minimum evidence перед done: проверка, что реализовано все, что описано в task.
- Phase 2 цель — prototype/proof of work. Не вылизывать архитектуру и не гнаться за скоростью.
- Код должен быть понятным, простым, модифицируемым и локальным.
- Нужны комментарии и docstrings, которые отвечают на вопрос: почему сделано именно так.
