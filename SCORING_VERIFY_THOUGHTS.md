# Как правильно оценивать результат: verify vs score

## Проблема

Сейчас, если `passed=False` (в т.ч. когда verification_command вернул ненулевой код), модель
получает штраф `failed_base * (2 - difficulty)`. Но `verify` — внешняя команда: она может
упасть по причинам, не связанным с работой модели:

- сломано тестовое окружение
- зависимость не установлена
- баг в самой проверке
- команда написана под другой ОС / путь

Штрафовать модель за это несправедливо и шумит сигнал.

---

## Что verify на самом деле говорит

| Ситуация | passed | verified | Что значит |
|---|---|---|---|
| Модель сделала правильно, verify прошёл | True | True | Всё хорошо |
| Модель сделала правильно, verify упал с ошибкой окружения | True | False | Не модели вина |
| Модель сделала неправильно, verify правомерно fail | False | False | Вина модели |
| Модель соврала о результате (false verification) | True → False | — | Самый плохой случай |

Сейчас поле `verified` — бинарное и не различает «провалился контент» vs «провалилась команда».

---

## Варианты решения

### Вариант A: Разделить `verified` на три состояния
```python
verify_status: Literal["passed", "content_failed", "command_error"] | None
```

- `passed` → бонус как сейчас
- `content_failed` → модель не выполнила задание, штраф обоснован
- `command_error` → не штрафуем, но и бонус не даём; логируем как «inconclusive»
- `None` → верификация не запускалась

**Плюсы:** точная атрибуция вины  
**Минусы:** нужно менять orchestrator, чтобы различал exit code != 0 по причине

### Вариант B: `verify` вообще не влияет на штраф, только на бонус
Штраф (`failed_base`) выставляется только явным человеческим гейтом (human gate).
Verify добавляет бонус `+verified` если прошёл, но его провал никогда не влечёт `-`.

**Плюсы:** просто, не шумит  
**Минусы:** модель не получает сигнала о том, что её результат не работает — 
только «нет бонуса», что слабый сигнал

### Вариант C: verify как prior, human gate как posterior
- `verify pass` → `passed = True`, даём бонус
- `verify fail (content)` → `passed` переходит в human review; человек решает
- `verify error (command)` → `passed` остаётся из human gate, verify игнорируется

Тут нужен отдельный флаг в event: `verify_exit_code`, `verify_stderr`.

---

## Моя рекомендация

**Вариант C** в упрощённой форме:

1. Orchestrator при запуске verification_command различает:
   - exit 0 → `verify_result = "ok"`
   - exit != 0, но stderr содержит признаки env-error (FileNotFoundError, ImportError, 
     connection refused, permission denied) → `verify_result = "env_error"`
   - exit != 0, чистый fail → `verify_result = "failed"`

2. В `score.record_ticket`:
   - `verified=True` только при `verify_result == "ok"`
   - Штраф `failed_base` только при явном `passed=False` из human gate,
     а не автоматически из verify
   - `verify_result == "env_error"` → не штраф, но в analysis флагируется как 
     «inconclusive verification» для диагностики сценария

3. `false_verification` (модель заявила успех, а verify провалился содержательно) 
   остаётся как самый тяжёлый штраф — это сигнал о галлюцинации.

---

## Что сейчас делать

- Поле `verify_result: str | None` добавить в audit event `ticket.scored`
- Orchestrator: при запуске verification_commands писать exit_code и первые 200 байт stderr
- `score.record_ticket`: принимать `verify_result` вместо `verified: bool`
- В visibility/analysis.py: отдельная секция «Inconclusive verifications» если env_error > 0

**Приоритет:** средний. Сейчас сценарии l01–l04 достаточно простые и verify-команды 
стабильны. Станет критично при l05+ с сетевыми/БД сценариями.
