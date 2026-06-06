# Архитектура

## Форма продукта

Planfoldr - детерминированный runtime для описания, запуска, тестирования и
инспекции многоцикловых агентных сценариев.

Главный пользователь на текущем этапе - разработчик, который описывает flow для
автоматизированной системы. Ценность Planfoldr не в визуальном конструкторе, а в
надежном способе:

- описать сценарий в YAML;
- запустить его через детерминированный runtime;
- проверить отдельные части через stub-модели;
- запустить более крупный e2e-сценарий через локальную модель Ollama;
- посмотреть, что произошло, в trace-файлах, live log и HTML-отчете.

Phase 2 уже реализована как MVP-прототип. Он умеет запускать сценарии, вести
бюджеты и permissions, валидировать outputs, повторять model tasks при
некорректном ответе, писать структурированный trace и собирать статический
HTML-отчет. Текущая линия развития после Phase 2 - более явная оркестрация
через persistent ticket tree в контексте run.

MVP-демо - e2e-сценарий, где локальная модель через Ollama создает простой
проект, например `cli-todo-list`, в отдельном workspace внутри `runs/`.
Flow должен произвести код, тесты и результат тестового запуска.

## Главный принцип

Модель не является центром управления.

Runtime контролирует:

- жизненный цикл scenario;
- жизненный цикл cycle;
- порядок выполнения tasks;
- переходы по typed outcomes;
- бюджеты;
- permissions;
- доступ к context и его изменение;
- validation и verification;
- audit, trace и report output.

Models являются executors внутри tasks типа `model`.

## Иерархия

```text
Scenario
  Cycle
    -> Task -> task -> task -> task -> task ->
    Cycle                             .^  |
      -> Task -> task -> task -> task `   `> task -> 
```

`Scenario` - весь запуск. Он владеет верхнеуровневой целью, required
conditions, constraints, budgets, inputs, outputs, cycles и context policy.

`Cycle` - единица управления flow. Cycles могут быть вложенными. Родительский и
дочерний cycles взаимодействуют только через явно описанные точки: child может
вернуть факты, requests или typed outcome вверх; parent может передать вниз
constraints, budgets, permissions и решения.

`Task` - пользовательский термин DSL для блока работы. Task имеет type, текст
задачи, input schema, output schema и executor. Во время выполнения task
порождает immutable result.

## Терминология

В реализации используется такая цепочка:

```text
Intent -> Task -> Execution -> Result
```

- `Intent`: зачем существует работа.
- `Task`: декларативная единица работы в scenario/cycle YAML.
- `Execution`: одна runtime-попытка выполнить task.
- `Result`: структурированный output, status, artifacts, budget usage и audit
  data.

Старый термин `Block` может встречаться в ранних заметках, но новые файлы и API
должны использовать `Task`.

## Контракт scenario

Корневой scenario YAML описывает запуск и ссылки на cycle-файлы. MVP-поля:

- `id`
- `goal`
- `required_conditions`
- `constraints`
- `budgets`
- `inputs`
- `outputs`
- `cycles`
- `context_policy`
- `defaults` для model/retry настроек, когда они нужны

Относительные ссылки на cycles и prompts resolve-ятся относительно файла, где
эта ссылка объявлена. Unknown fields отклоняются схемой: неявные настройки лучше
считать ошибкой, чем молча принимать.

## Контракт cycle

Cycle YAML описывает локальный flow. MVP-поля:

- `id`
- `goal`
- `entrypoint`
- `tasks`
- `links`
- `nested_cycles`
- `budgets`
- `constraints`
- `context_access`

`entrypoint` задает первую task. `links` отображают enum outcomes tasks в
следующие tasks, запросы к parent, запуск child-cycle или terminal states.
Текущий MVP runtime выполняет cycle последовательно; параллельность остается
целевой архитектурой, а links уже задают будущие точки синхронизации.

## Контракт task

Task YAML задает одну исполняемую единицу. MVP-поля:

- `id`
- `type`
- `task`
- `input_schema`
- `output_schema`
- `executor`

Поддерживаемые типы task:

- `command`
- `model`
- `tool`
- `verify`

Verifier behavior моделируется отдельными tasks типа `verify`, а не скрытым
свойством каждой task. Output каждой task должен проходить JSON Schema
validation и содержать поле `status`.

## Outcomes

MVP task и cycle outcomes:

- `success`
- `failure`
- `budget_exceeded`
- `need_context`
- `need_decision`
- `need_answer`
- `need_inner_cycle`
- `need_permission`
- `need_tool`
- `need_tool_call`
- `retry_exceeded`

Каждый non-success outcome должен включать structured reason и достаточно
evidence, чтобы parent cycle мог решить, что делать дальше.

## Flow и branching

MVP branching основан на enum outcomes.

Пример:

```text
task.create_code -> success -> task.run_tests
task.create_code -> need_context -> parent.request_context
task.create_code -> failure -> task.inspect_failure
```

Terminal targets в links:

- `success` - cycle завершился успешно;
- `fail` - cycle завершился ошибкой;
- `parent` - control возвращается parent cycle вместе с outcome/request.

Parallel execution входит в целевую архитектуру. Для MVP каждый cycle
выполняется последовательно. В будущем cycles могут выполняться в отдельных
threads или async tasks, а links будут определять sync points. Parent task может
ждать один child result или все child results.

## Context model

Context имеет уровни:

- task context и state;
- cycle context и state;
- scenario context и state;
- decision log;
- audit log.

Каждая task и cycle объявляет read/write/delete доступ к sections контекста.

Defaults:

- каждая task может свободно менять свой private context;
- каждая task может читать разрешенный parent context;
- запись в parent или scenario context требует явного permission;
- все context mutations являются audit events.

Важное правило:

```text
facts go up
constraints go down
```

Факты не поднимаются вверх как произвольный dump данных. Child cycle сообщает
результат parent cycle через заранее специфицированный output/request shape.

## Constraints и permissions

Есть две категории ограничений:

- verifiable constraints, которые проверяются verifier tasks;
- capability constraints, которые определяют, что scenario, cycle или task
  вообще имеют право делать.

MVP permission enforcement:

- tool allowlist/denylist;
- command allowlist/blacklist по regex;
- filesystem allowlists для чтения и записи через normalized resolved paths.

Permissions текут от внешних cycles к внутренним. Inner cycles могут запросить
дополнительные permissions через typed outcome `need_permission`.

## Budgets

MVP budgets:

- `max_iterations`
- `max_tool_calls`
- `max_model_calls`
- `max_model_budget`
- `max_cpu_time`
- `max_ram`

Cycle может тратить budget напрямую или делегировать часть budget nested cycles.
В текущем MVP RAM budget фиксируется как unsupported/placeholder, а не
enforce-ится.

При исчерпании budget runtime возвращает `budget_exceeded` с отчетом. Parent
cycle решает: увеличить budget, остановиться, попробовать другой путь или
завершить flow ошибкой.

## Executors

MVP executor types:

- `command`
- `model`
- `tool` для ограниченных внутренних операций

Verifier tasks могут использовать:

- command execution;
- schema validation;
- custom script;
- model request с verification prompt.

Model selection задается явно для model task, со scenario defaults как fallback.
Реализованы stub model executor для детерминированных тестов и Ollama executor
для локального e2e-демо.

Internal operations, например материализация файлов из структурированного model
output, представлены constrained tools. Они не должны превращаться в
произвольные shell snippets.

## Prompts

Prompts - versioned templates с:

- `id`
- content hash;
- variables;
- rendered prompt captured in audit;
- prompt id и variable values captured in trace.

Prompt files лежат отдельно от scenario/cycle YAML и подключаются через
executor prompt reference. Это позволяет trace-ить, какой именно prompt был
отрендерен и какой model response был получен.

## Output validation и retries

Model outputs должны валидироваться против task `output_schema`.

При invalid output runtime:

- учитывает попытку в budgets;
- делает retry настроенное число раз;
- добавляет schema clarification в retry prompt;
- возвращает `retry_exceeded`, если attempts исчерпаны.

Command/tool outputs также возвращают structured task result. Ошибки executor,
non-zero command exit или schema validation failures должны попадать в result,
trace и report как inspectable evidence.

## Verification

Required conditions представлены цепочкой verifier tasks.

Cycle считается successful, когда его verifier tasks проходят. Для MVP verifier
evidence записывается в run trace и HTML report. Completion, особенно в будущей
ticket-tree orchestration, не должна зависеть только от model text: нужен
verifier evidence или явное human/system decision, если scenario это разрешает.

## Trace, replay и reporting

MVP output включает:

- live CLI/log events в `logs/execution.log`;
- structured machine-readable trace под `trace/`;
- model stream artifacts: `stream.jsonl`, `assembled.txt`, `content.txt`,
  `thinking.txt`, когда provider их дает;
- refresh-friendly `trace/report_data.json`;
- статический one-page `report.html`.

Для воспроизводимости trace захватывает:

- full input;
- full output;
- model request и response;
- tool/command execution result;
- budgets before/after execution;
- config version или hash;
- prompt id, variables и rendered prompt;
- artifacts produced by tasks.

MVP replay scope - task replay. Full scenario replay может быть следующим
крупным этапом. Сравнение runs в MVP ограничено final status comparison; более
семантический diff остается вне базового Phase 2 scope.

HTML report должен показывать execution structure и позволять смотреть поведение
model step by step. Более глубокие nested levels можно скрывать, но важная
информация не должна существовать только в collapsed JSON.

## Run artifacts и workspaces

Generated run artifacts принадлежат `runs/` и не коммитятся.

Типичная структура run:

```text
runs/<scenario_id>/
  <run_id>/
    logs/
      execution.log
    trace/
      manifest.json
      scenario.json
      report_data.json
      tasks/executions.json
      cycles/index.json
    workspace/
    report.html
```

Scenario YAML должен использовать `{{ runtime.run_dir }}` и
`{{ runtime.workspace_dir }}` вместо shared paths. Generated projects должны
появляться внутри `{{ runtime.workspace_dir }}/project`, чтобы каждый run был
изолирован, а старые logs и traces оставались inspectable.

## Ticket-tree orchestration

Следующий архитектурный слой - persistent ticket tree в context.

Идея: верхнеуровневый planning/orchestration cycle владеет деревом tickets, а
nested execution cycles берут отдельные ready tickets, выполняют работу,
прикрепляют evidence/artifacts и возвращают результат наверх. Ticket может
представлять research, documentation, code, tests, manual_testing, verification
или orchestration.

Базовая ticket shape:

- stable `id`;
- `title`;
- `description`;
- `type`;
- dependencies;
- status;
- owner;
- links to evidence, artifacts, audit events, decisions и trace records.

Базовые statuses:

- `blocked`
- `ready`
- `running`
- `needs_review`
- `done`
- `failed`
- `cancelled`

Уже есть начальные deterministic helpers для ticket schema, readiness,
assignment и completion rules. Но ticket tree пока не является end-to-end
оркестратором runtime: он еще должен быть связан с persisted context, explicit
trace events, nested cycle handoff, budget accounting и report view.

Целевое правило: nested cycles могут обновлять назначенные им tickets, но не
могут объявить все дерево завершенным. Только top-level orchestration cycle
владеет целостностью ticket tree и final completion.

## Текущие границы MVP

Что уже является рабочей частью Phase 2:

- Python package `planfoldr`;
- YAML scenario/cycle/prompt loader;
- Pydantic schemas с rejected unknown fields;
- deterministic sequential runtime loop;
- explicit outcomes and links;
- scoped context, state, audit primitives и decision log;
- budget tracking и permission guards;
- command, tool, stub model и Ollama executors;
- output validation, retry handling и verifier evidence;
- structured trace writer, task replay и static HTML report;
- deterministic stub e2e scenarios;
- optional local Ollama demo.

Что остается за пределами текущего MVP, пока отдельная quest не требует иного:

- visual scenario builder;
- distributed execution;
- full sandboxing;
- true parallel DAG scheduling;
- full scenario replay;
- semantic run diff;
- automatic model routing;
- production CI integration;
- complete ticket-tree runtime orchestration;
- ticket tree report view;
- real nested-cycle budget delegation.
