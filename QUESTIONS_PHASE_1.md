# Questions Phase 1

Список вопросов для первичной проработки Planfoldr и выбора формы MVP.

У каждого вопроса есть четыре варианта ответа:
- Просто — минимальное решение для быстрого MVP.
- Среднесложно — решение с умеренной гибкостью.
- Сложно — решение для более серьезного продукта.
- Архитектурно дальновидно — вариант, который закладывает долгосрочную модель системы.

## 1. Пользователь и ценность

### 1. Кто первый пользователь Planfoldr?

- Ответ:
- Просто: solo-разработчик, который запускает сценарии локально через CLI.
- Среднесложно: небольшая команда, которая хочет повторяемые сценарии для типовых задач разработки.
- Сложно: engineering-команда, интегрирующая Planfoldr в CI/CD и PR-процессы.
- Архитектурно дальновидно: платформа для построения проверяемых агентных процессов поверх разных моделей, инструментов и сред исполнения.

### 2. Какую боль MVP должен закрыть первой?

- Ответ:
- Просто: показать, что сценарий можно запустить пошагово и получить понятный execution log.
- Среднесложно: сделать воспроизводимым один полезный flow, например анализ падения теста.
- Сложно: снизить количество пропущенных шагов и ручной проверки в реальном dev-процессе.
- Архитектурно дальновидно: отделить управление процессом от модели и сделать модель только исполнителем внутри проверяемых блоков.

### 3. Что пользователь получает на выходе сценария?

- Ответ:
- Просто: финальный статус, лог шагов и краткий отчет.
- Среднесложно: structured output каждого блока, итоговый отчет и список измененных фактов контекста.
- Сложно: patch, проверки, причины решений, trace исполнения и machine-readable result.
- Архитектурно дальновидно: полный audit trail, пригодный для replay, сравнения запусков и автоматической верификации.

### 4. Какой сценарий выбрать для MVP?

- Ответ:
- Просто: "запустить команду, собрать вывод, сделать summary".
- Среднесложно: "проанализировать падение теста и предложить patch".
- Сложно: "исправить падающий тест, применить изменения и проверить результат".
- Архитектурно дальновидно: "многоцикловое исправление теста с бюджетами, typed transitions и explicit context updates".

## 2. Базовые сущности

### 5. Чем Scenario отличается от Cycle?

- Ответ:
- Просто: Scenario — весь запуск, Cycle — повторяемая часть внутри него.
- Среднесложно: Scenario содержит цель, НУ, бюджеты и набор циклов; Cycle содержит блоки и правила повторения.
- Сложно: Scenario задает внешний contract, Cycle задает управляемый loop с собственными входами, выходами, бюджетами и ограничениями.
- Архитектурно дальновидно: Scenario — orchestration boundary, Cycle — composable control-flow unit, который можно вкладывать, переиспользовать и тестировать отдельно.

### 6. Что такое Block?

- Ответ:
- Просто: один исполняемый шаг.
- Среднесложно: шаг с типом, входом, выходом, ограничениями и бюджетом.
- Сложно: атомарная task-единица с typed input/output, executor, validation и transition result.
- Архитектурно дальновидно: контрактная capability-единица, отделенная от конкретного исполнителя: model, command, human, verifier, context updater.

### 7. Нужно ли переименовывать Block в Task?

- Ответ:
- Просто: оставить Block до конца MVP.
- Среднесложно: использовать Task в пользовательском DSL, но сохранить Block как внутренний термин.
- Сложно: развести Task как намерение и Block как исполняемый runtime step.
- Архитектурно дальновидно: построить терминологию вокруг Intent -> Task -> Execution -> Result, чтобы не смешивать описание работы и факт исполнения.

### 8. Какие поля обязательны для Scenario?

- Ответ:
- Просто: id, goal, blocks.
- Среднесложно: id, goal, success_conditions, budgets, cycles.
- Сложно: id, goal, required_conditions, constraints, budgets, inputs, outputs, cycles, context_policy.
- Архитектурно дальновидно: formal contract: purpose, invariants, permissions, budgets, lifecycle, context model, observability policy, replay policy.

### 9. Какие поля обязательны для Cycle?

- Ответ:
- Просто: id, blocks, max_iterations.
- Среднесложно: id, entrypoint, blocks, transitions, budget.
- Сложно: id, entry_contract, exit_contract, blocks, transitions, nested_cycles, budgets, constraints.
- Архитектурно дальновидно: reusable control-flow component with typed ports, feedback points, override policy and parent-child communication rules.

### 10. Какие поля обязательны для Block?

- Ответ:
- Просто: id, type, input, output.
- Среднесложно: id, type, task, input_schema, output_schema, executor.
- Сложно: id, task, constraints, budget, permissions, input_schema, output_schema, verifier, transition_mapping.
- Архитектурно дальновидно: declarative contract plus runtime binding: capability, executor selection, provenance, validation, retry policy, observability and deterministic replay metadata.

## 3. Flow и ветвления

### 11. Как описывать переходы между блоками?

- Ответ:
- Просто: next_block_id.
- Среднесложно: branch по enum-статусу output блока.
- Сложно: typed transitions с условиями на структурированный output.
- Архитектурно дальновидно: формальная transition system с валидируемыми guards, typed ports и возможностью статического анализа сценария.

### 12. Какие статусы исполнения нужны в MVP?

- Ответ:
- Просто: success, failure.
- Среднесложно: success, failure, needs_input, budget_exceeded.
- Сложно: success, failure, retry, skipped, blocked, needs_parent, needs_inner_cycle.
- Архитектурно дальновидно: единая outcome-модель с причинами, severity, recoverability и machine-actionable next steps.

### 13. Что делать при ошибке блока?

- Ответ:
- Просто: остановить сценарий.
- Среднесложно: retry один раз и потом остановить.
- Сложно: retry/fallback/ask parent в зависимости от типа ошибки.
- Архитектурно дальновидно: error handling как часть declarative policy: recovery strategy, escalation path, budget impact, audit event.

### 14. Нужен ли parallel execution в MVP?

- Ответ:
- Просто: нет, только последовательные шаги.
- Среднесложно: нет в runtime, но DSL не должен мешать добавить параллельность позже.
- Сложно: поддержать независимые parallel branches для command/verify блоков.
- Архитектурно дальновидно: DAG + nested cycles + deterministic join semantics + conflict resolution.

## 4. Контекст

### 15. Что считается контекстом?

- Ответ:
- Просто: текстовое поле, которое передается между шагами.
- Среднесложно: набор key-value фактов и заметок сценария.
- Сложно: несколько уровней: block context, cycle context, scenario context.
- Архитектурно дальновидно: typed context graph с provenance, scope, lifetime, access rules и explicit mutations.

### 16. Как обновляется контекст?

- Ответ:
- Просто: каждый блок может добавить текст в общий лог.
- Среднесложно: только специальные context_update блоки меняют контекст.
- Сложно: обновления проходят schema validation и фиксируются как events.
- Архитектурно дальновидно: immutable event log + derived context snapshots + replayable context evolution.

### 17. Может ли блок читать глобальный контекст напрямую?

- Ответ:
- Просто: да, весь контекст передается каждому блоку.
- Среднесложно: блок получает только выбранные поля контекста.
- Сложно: доступ к контексту задается в контракте блока.
- Архитектурно дальновидно: capability-based context access with scoped views, redaction and deterministic context builders.

### 18. Как предотвратить утекание и забывание контекста?

- Ответ:
- Просто: сохранять все outputs в лог.
- Среднесложно: явно выбирать факты, которые поднимаются наверх.
- Сложно: разделить ephemeral notes, verified facts и decisions.
- Архитектурно дальновидно: facts go up, constraints go down, все изменения контекста проходят typed contracts и provenance tracking.

## 5. НУ, ограничения и верификация

### 19. Что такое НУ в MVP?

- Ответ:
- Просто: текстовое описание условия успеха.
- Среднесложно: список проверок, которые надо выполнить перед success.
- Сложно: machine-checkable conditions: команды, схемы, diff checks, custom validators.
- Архитектурно дальновидно: formal success contract, связывающий цель, constraints, verification blocks и evidence.

### 20. Какие verify-блоки нужны первыми?

- Ответ:
- Просто: command exits with 0.
- Среднесложно: command, file_exists, schema_validation.
- Сложно: command, diff_check, regex_check, json_schema, custom_script.
- Архитектурно дальновидно: pluggable verification framework with evidence artifacts and deterministic replay.

### 21. Где живут ограничения?

- Ответ:
- Просто: внутри Scenario как текст.
- Среднесложно: на уровне Scenario и Block.
- Сложно: Scenario/Cycle/Block имеют свои constraints, которые наследуются вниз.
- Архитектурно дальновидно: constraints are first-class policies: composable, enforceable, inherited, overridable only by parent.

### 22. Как понять, что цель достигнута?

- Ответ:
- Просто: последний блок вернул success.
- Среднесложно: все required verify-блоки успешны.
- Сложно: выполнены НУ, не нарушены constraints, бюджет не превышен, output валиден.
- Архитектурно дальновидно: success is a typed terminal state backed by evidence, audit trace and contract satisfaction proof.

## 6. Бюджеты и доступы

### 23. Какие бюджеты нужны в MVP?

- Ответ:
- Просто: max_iterations.
- Среднесложно: max_iterations, max_commands, max_model_calls.
- Сложно: time, tokens, money, commands, retries, filesystem writes.
- Архитектурно дальновидно: unified resource budget model with deterministic accounting and parent-child budget delegation.

### 24. Что делать при превышении бюджета?

- Ответ:
- Просто: остановить сценарий.
- Среднесложно: вернуть budget_exceeded с отчетом.
- Сложно: запросить parent decision или перейти в fallback.
- Архитектурно дальновидно: budget exhaustion is a typed control-flow event with policy-driven recovery and audit trail.

### 25. Как задаются доступы?

- Ответ:
- Просто: списком разрешенных command types.
- Среднесложно: allowlist tools и filesystem paths.
- Сложно: permissions per Scenario/Cycle/Block.
- Архитектурно дальновидно: capability model with scoped grants, deterministic enforcement and parent-controlled delegation.

### 26. Нужно ли реально enforce-ить доступы в MVP?

- Ответ:
- Просто: нет, только описывать в конфиге.
- Среднесложно: валидировать config и запрещать неизвестные tool types.
- Сложно: enforce-ить command allowlist и filesystem scope.
- Архитектурно дальновидно: sandboxed execution with auditable permissions and policy engine.

## 7. Модели и исполнители

### 27. Какие типы исполнителей нужны в MVP?

- Ответ:
- Просто: command и model.
- Среднесложно: command, model, verify, context_update.
- Сложно: command, model, verify, human_input, file_patch, context_update.
- Архитектурно дальновидно: executor registry with typed capabilities, versioning, policies and deterministic result envelopes.

### 28. Как выбирать модель для блока?

- Ответ:
- Просто: одна модель на весь сценарий.
- Среднесложно: model задается явно в каждом model-блоке.
- Сложно: model выбирается через policy по типу задачи и бюджету.
- Архитектурно дальновидно: model routing as deterministic policy with constraints, fallback, cost accounting and quality gates.

### 29. Что делать с невалидным output модели?

- Ответ:
- Просто: считать блок failed.
- Среднесложно: один retry с уточнением схемы.
- Сложно: repair pass, retry budget, fallback model, then failure.
- Архитектурно дальновидно: structured output validation pipeline with repair, provenance, confidence and typed failure reasons.

### 30. Должны ли prompts быть версионируемыми?

- Ответ:
- Просто: нет, prompt хранится прямо в block config.
- Среднесложно: prompt хранится отдельно и имеет id/version.
- Сложно: prompt templates с variables, schema и тестами.
- Архитектурно дальновидно: prompt artifacts as versioned executable specs with evaluation history and compatibility metadata.

## 8. Детерминизм и replay

### 31. Что нужно сохранять для воспроизводимости?

- Ответ:
- Просто: execution log.
- Среднесложно: input/output каждого блока и использованные команды.
- Сложно: model request/response, command output, timestamps, budgets, config version.
- Архитектурно дальновидно: complete run trace with tool artifacts, environment fingerprints, model metadata and replay modes.

### 32. Нужно ли replay в MVP?

- Ответ:
- Просто: нет.
- Среднесложно: replay только по сохраненным outputs без повторного исполнения.
- Сложно: replay отдельных блоков и всего сценария.
- Архитектурно дальновидно: deterministic replay engine with mocked tools, snapshot comparison and divergence detection.

### 33. Как сравнивать два запуска?

- Ответ:
- Просто: сравнивать финальный статус.
- Среднесложно: сравнивать sequence блоков и их outcomes.
- Сложно: сравнивать typed outputs, budgets, context updates и artifacts.
- Архитектурно дальновидно: semantic run diff with deterministic/expected/nondeterministic regions.

## 9. Формат и интерфейс MVP

### 34. Какой формат описания сценариев выбрать?

- Ответ:
- Просто: JSON.
- Среднесложно: YAML.
- Сложно: TypeScript/Python DSL плюс экспорт в JSON.
- Архитектурно дальновидно: declarative schema as source of truth, with multiple frontends: YAML, SDK, visual editor.

### 35. Каким должен быть первый интерфейс?

- Ответ:
- Просто: CLI runner.
- Среднесложно: CLI runner плюс human-readable run report.
- Сложно: CLI, local web viewer для trace и конфигурационный валидатор.
- Архитектурно дальновидно: runtime + authoring tools + observability UI + CI integration.

### 36. Нужна ли UI-визуализация flow в MVP?

- Ответ:
- Просто: нет.
- Среднесложно: текстовая схема или Mermaid export.
- Сложно: HTML trace viewer.
- Архитектурно дальновидно: visual scenario builder with typed contracts, live validation and run inspection.

### 37. Какой критерий готовности MVP?

- Ответ:
- Просто: один сценарий запускается end-to-end и пишет лог.
- Среднесложно: один сценарий имеет typed outputs, budgets и verification.
- Сложно: сценарий можно воспроизвести, протестировать и сравнить с предыдущим запуском.
- Архитектурно дальновидно: MVP доказывает главный принцип: model is not the controller, controller is deterministic and auditable.

## 10. Что сознательно не делать в Phase 1

### 38. Что исключить из MVP?

- Ответ:
- Просто: nested cycles, replay, UI, permissions enforcement, model routing.
- Среднесложно: исключить UI и parallelism, но оставить typed contracts и context updates.
- Сложно: исключить только distributed execution и full sandboxing.
- Архитектурно дальновидно: Phase 1 должен быть маленьким, но не противоречить будущим nested cycles, replay, policies and observability.

### 39. Как избежать переусложнения?

- Ответ:
- Просто: реализовать один сценарий и один формат конфига.
- Среднесложно: ограничить количество block types и transition types.
- Сложно: формально зафиксировать scope Phase 1 и Phase 2.
- Архитектурно дальновидно: разделить stable core contracts и experimental adapters, чтобы MVP был маленьким, но архитектурно честным.

### 40. Что должно быть главным артефактом Phase 1?

- Ответ:
- Просто: README с описанием MVP.
- Среднесложно: scenario schema и один runnable example.
- Сложно: runtime prototype, schema validation, example scenario, run trace.
- Архитектурно дальновидно: executable specification: schema, tests, examples, trace format and clear boundaries of deterministic control.
