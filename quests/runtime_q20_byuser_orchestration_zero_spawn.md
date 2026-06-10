# Task runtime_q20_byuser_orchestration_zero_spawn: Защита от нулевого спауна оркестрации
File name: `runtime_q20_byuser_orchestration_zero_spawn.md`

## Статус

Текущий статус: active
Блокирован: нет
Описание: Цикл оркестрации, породивший ноль под-тикетов, всегда помечается `done`,
потому что тип тикета orchestration пропускает обе фазы верификации, делая `passed=True`
безусловно. Когда модель возвращает пустой контент (например, HTTP 500 от модели,
не умеющей обрабатывать `<tool_call>` в системном промпте), оркестрация молча «успешно
завершается» без поставленных задач, цикл-исполнитель не находит ничего для выполнения,
а финальная верификация проваливает каждую команду, потому что код не был написан.
Сбой невидим до самого конца.

## Цель

Сделать нулевой спаун оркестрации детектируемым, отображаемым и исправимым сбоем харнесса,
а не молчаливым ложным успехом.

## Конкретный наблюдённый сбой

Запуск `mini_httpd_local_l14.yaml` с `qwen3-coder:30b`:
- `qwen3-coder:30b` падает с HTTP 500 на любом промпте, содержащем `<tool_call>` XML.
- `OllamaModel.generate()` перехватывает HTTPError как OSError и возвращает
  `ModelResponse(content="", available=False, tokens=0)`.
- Цикл действий получает ошибки разбора на всех 4 итерациях, сжигает retry-попытки, завершается.
- `_finalize` для тикета типа `orchestration`: `cmd_ok=True, model_ok=True, passed=True`
  (фазы верификации не запускаются для orchestration), тикет → `done`, очки +4.
- `_executor_loop` находит 0 готовых тикетов, немедленно завершается.
- Финальная верификация запускает 11 команд, все проваливаются (ничего не построено).
- `analysis.md` называет это «failed», но первопричина — оркестрация с нулевым спауном —
  не названа.

## Необходимые условия

- Цикл оркестрации, завершившийся с нулевым спауном тикетов, НЕ должен помечаться `done`.
  Он должен повторяться (до `max_attempts`) или, при исчерпании, завершаться с явной причиной.
- Когда вызов модели возвращает `available=False` или пустой контент, ошибка должна быть
  видна в терминальном потоке и в `audit.jsonl` как именованное событие, а не молча проглатываться.
- Вывод в терминале должен показывать строку предупреждения, когда любой вызов модели в цикле
  возвращает пустой контент (например, `⚠️  model returned empty response (available=False): <reason>`).
- `analysis.md` должен перечислять нулевой спаун оркестрации как отдельную сигнатуру сбоя
  с ответственной моделью и причиной HTTP-ошибки, если известна.

## TODO

### RnD

1. Перечитать `src/planfoldr/cycle.py::_finalize` и `PHASES_BY_TYPE`, чтобы подтвердить,
   почему тикеты orchestration всегда проходят независимо от вывода модели.

   Верифицировать: записать точные номера строк и значения переменных (`cmd_ok`, `model_ok`,
   `passed`) для типа orchestration в Примечаниях к реализации этого квеста.

2. Перечитать `src/planfoldr/model.py::OllamaModel.generate()`, чтобы подтвердить, что
   возвращается при `HTTPError` или `URLError`, и что содержат `response.available`
   и `response.raw`.

   Верифицировать: записать точный путь возврата и какие поля несут причину ошибки.

3. Перечитать `src/planfoldr/cycle.py::_action_loop` и `_one_action`, чтобы подтвердить,
   что пустой контент и `available=False` обрабатываются так же, как ошибка разбора
   (retry reformat), и что нет раннего выхода или эскалации при сбое соединения.

   Верифицировать: записать путь retry reformat и подтвердить, что `available=False`
   нигде не проверяется.

4. Перечитать `src/planfoldr/orchestrator.py::_run_top_cycle` и `_executor_loop`, чтобы
   подтвердить, что нулевой спаун тикетов вызывает немедленный выход цикла-исполнителя
   без диагностики.

   Верифицировать: проследить путь `spawned_tickets == []` от `_run_top_cycle` через
   `_executor_loop` до `_final_verification`.

5. Проверить `src/planfoldr/visibility/analysis.py::build_analysis` и `analysis.md`
   из провального запуска в `runs/2026-06-10_22-53-07__run_2ea4f9c9cb4a/analysis.md`,
   чтобы подтвердить, что нулевой спаун оркестрации не называется как сигнатура сбоя.

   Верифицировать: записать, какие сигнатуры сбоев сейчас детектируются, а какие — нет.

### Реализация

6. В `src/planfoldr/cycle.py::_finalize` добавить защиту от нулевого спауна для тикетов
   типа orchestration: если `self.ticket.type in ("orchestration", "decompose", "plan")`
   и `len(self.spawned_tickets) == 0` и цикл не был прерван по бюджету, не помечать тикет
   `done` — вместо этого пометить его `needs_review` с причиной
   `"orchestration produced no tickets; retry"`.

   Очки не должны получать бонус успеха на этом пути. Сохранить существующую логику
   `passed=True` для случая, когда тип тикета законно не требует спауна (т.е. добавить
   предикат, а не широкую проверку типа).

   Верифицировать: добавить `tests/test_cycle_stub.py::test_orchestration_zero_spawn_needs_review` —
   использовать StubModel, который возвращает действия `plan`, но никогда `create_ticket`;
   убедиться, что результат цикла `needs_review`, очки не получают бонус успеха, а причина
   содержит "no tickets".

7. В `src/planfoldr/cycle.py::_one_action` проверять `response.available` сразу после
   `self.model.generate()`. При `available=False` испускать отдельное stream-событие
   `"model_unavailable"` с `reason=response.raw` (строка ошибки) и возвращать
   `Action(action="", error=f"model unavailable: {response.raw}")` без сжигания
   retry reformat.

   Верифицировать: добавить `tests/test_cycle_stub.py::test_model_unavailable_returns_error_action` —
   использовать подкласс ModelAdapter, возвращающий `ModelResponse(available=False, raw="HTTP 500")`;
   убедиться, что возвращённый Action имеет `error`, retry reformat не потребляются, а
   stream_sink получает событие `"model_unavailable"` с причиной.

8. В `src/planfoldr/visibility/terminal.py` (или где рендерятся терминальные stream-события)
   добавить обработчик событий `"model_unavailable"`, выводящий видимую строку предупреждения,
   например: `│  ⚠️  model unavailable: HTTP Error 500: Internal Server Error`.

   Верифицировать: добавить тест или ручную проверку, подтверждающую появление предупреждения
   в выводе терминала при `available=False`.

9. В `src/planfoldr/visibility/analysis.py::build_analysis` добавить детектирование
   сигнатуры нулевого спауна оркестрации: когда тикет orchestration имеет статус
   `needs_review` или `failed` и количество порождённых тикетов равно 0, испустить
   именованную сигнатуру сбоя `"zero_spawn_orchestration"` с id цикла, моделью и
   любой причиной model_unavailable из лога аудита.

   Верифицировать: запустить stub-сценарий из TODO 6 и убедиться, что `analysis.md`
   перечисляет `zero_spawn_orchestration` в разделе "What went wrong".

### Верификация

10. Запустить сфокусированные тесты цикла:
    `.venv/bin/python -m pytest tests/test_cycle_stub.py -q -k "orchestration or unavailable"`.

    Верифицировать: оба новых теста проходят; существующие тесты цикла не регрессируют.

11. Запустить полный набор по умолчанию:
    `.venv/bin/python -m pytest -q`.

    Верифицировать: все тесты проходят; записать количество опциональных Ollama-пропусков.

12. Запустить stub e2e-сценарий и проверить артефакты директории запуска:
    `.venv/bin/python -m pytest tests/test_e2e_stub.py -q`.

    Верифицировать: статус и причина `result.json`, статус тикета оркестрации в
    `tickets.json` и сигнатура zero-spawn в `analysis.md` — все присутствуют
    и согласованы.

## Финальная верификация

- Перечитать этот квест и подтвердить, что каждый пункт TODO имеет доказательство реализации
  или конкретную заметку об отложении.
- Перечитать примеры `AGENTS.md` и подтвердить, что ни один красивый пример не был удалён.
- Запустить сфокусированные тесты цикла и `.venv/bin/python -m pytest -q`.
- Напрямую проверить `analysis.md` и `result.json` хотя бы одного сгенерированного запуска.
- Переместить квест в `quests/done/` только в том же коммите, что реализует и верифицирует исправления.

## Примечания к реализации

Первопричина (подтверждена расследованием 2026-06-10):

- `src/planfoldr/cycle.py::PHASES_BY_TYPE["orchestration"] = [CONTEXT, CHANGES]` — нет фаз
  верификации, поэтому `_finalize` всегда вычисляет `cmd_ok=True, model_ok=True, passed=True`.
- `src/planfoldr/model.py::OllamaModel.generate()` строки 243-246 — HTTPError перехватывается
  как OSError, возвращает `ModelResponse(content="", available=False, raw=str(exc))`.
- `src/planfoldr/cycle.py::_one_action` — никогда не проверяет `response.available`;
  `parse_action("")` возвращает ошибочный Action, который сжигает retry reformat, но не эскалирует.
- `src/planfoldr/orchestrator.py::_run_top_cycle` вызывает `_run_cycle` и отбрасывает результат;
  `_executor_loop` затем находит нет готовых тикетов и молча завершается.
- Подтверждённый триггер: `qwen3-coder:30b` возвращает HTTP 500 всегда, когда `<tool_call>`
  появляется в системном сообщении — харнесс всегда включает его в `_PROTOCOL`.
- Исправление не должно менять поведение прохождения тикетов оркестрации, которые корректно
  спаунят тикеты (обычный случай); оно ловит только edge-case нулевого спауна.
