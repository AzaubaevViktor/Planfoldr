# Task arch_q04_no_cross_run_persistence: KB и ScoreSystem не сохраняются между запусками — харнес не учится
File name: `arch_q04_no_cross_run_persistence.md`

## Статус

Текущий статус: active
Блокирован: нет
Описание: `KnowledgeBase` и `ScoreSystem` создаются заново при каждом запуске `Orchestrator`.
Файлы `kb.json` и `scores.json` записываются в конце run, но никогда не читаются при старте
следующего. Цикл хардения из INTERFACE.md — «запустить задачи → прочитать Run Analysis → внести
улучшения → повторить» — предполагает, что харнес накапливает знания между итерациями. Сейчас
каждый запуск начинается с нуля: модели не имеют репутации, KB не хранит ни исследований, ни
архитектурных решений из предыдущих запусков.

---

## Конкретная дыра

### `orchestrator.py` — ScoreSystem создаётся fresh каждый раз

```python
# __init__, строка 153
self.score = ScoreSystem(self.audit)
# ← scores.json прошлого запуска никогда не загружается
```

`scores.json` пишется в `_persist()`, но `Orchestrator.__init__` его не читает.

### `orchestrator.py` — KnowledgeBase создаётся пустой каждый раз

```python
# __init__, строка 152
self.kb = KnowledgeBase(self.audit)
# ← kb.json прошлого запуска никогда не загружается
```

`kb.json` пишется в `_persist()` через `self.kb.to_dict()`, но `KnowledgeBase` не имеет метода
`from_dict()` и не загружается при старте.

### Что теряется между запусками

**ScoreSystem**: какая модель лучше работает для `research`/`code`/`verify` задач. Без этого
каждый запуск выбирает модель по размеру параметров (base score), игнорируя историю провалов.

**KnowledgeBase**: результаты исследовательских тикетов (архитектура решения, анти-паттерны,
выбранные библиотеки). Каждый запуск типа «напиши REST API» заново исследует то, что уже было
исследовано в предыдущем.

---

## Что должно быть исправлено

### Часть A: Загрузка ScoreSystem из предыдущего запуска

Добавить `ScoreSystem.from_dict(d)` — статический метод, который восстанавливает `ModelScore`
из словаря:

```python
@staticmethod
def from_dict(d: dict, *, audit=None) -> "ScoreSystem":
    ss = ScoreSystem(audit=audit)
    for model_id, ms in d.items():
        ss.scores[model_id] = ModelScore(
            model_id=model_id,
            base=ms["base"], global_score=ms["global_score"],
            by_role=dict(ms["by_role"]), by_task_type=dict(ms["by_task_type"]),
            consecutive_fails=dict(ms["consecutive_fails"]), tickets=ms["tickets"],
        )
    return ss
```

В `Orchestrator.__init__`, принять опциональный параметр `seed_scores: Optional[Path] = None`.
Если путь передан и файл существует — загрузить через `ScoreSystem.from_dict(json.loads(...))`.

### Часть B: Загрузка KnowledgeBase из предыдущего запуска

Добавить `KnowledgeBase.from_dict(d)`:

```python
@staticmethod
def from_dict(d: dict, *, audit=None) -> "KnowledgeBase":
    kb = KnowledgeBase(audit=audit)
    for name, section in d.items():
        kb.create_section(name,
            read_roles=set(section.get("read_roles", ["*"])),
            write_roles=set(section.get("write_roles", ["*"])),
            content=section.get("content", ""),
        )
    return kb
```

В `Orchestrator.__init__`, принять `seed_kb: Optional[Path] = None`. Если путь передан —
загрузить KB через `KnowledgeBase.from_dict(json.loads(...))`.

### Часть C: CLI-поддержка `--seed-scores` и `--seed-kb`

В `cli.py` добавить аргументы:
```
--seed-scores PATH   load scores from a previous run's scores.json
--seed-kb     PATH   load knowledge base from a previous run's kb.json
```

Передавать пути в `Orchestrator(scenario, seed_scores=..., seed_kb=...)`.

### Часть D: Стратегия «последний запуск сценария как seed»

Опциональная удобная функция: если `--seed-scores auto` — искать самый свежий `runs/*/scores.json`
по сценарию и загружать его. Это не блокирует квест, но нужно отметить как future work.

---

## TODO

### RnD
1. Прочитать `src/planfoldr/score.py` — убедиться, что `to_dict()` содержит все поля,
   нужные для `from_dict()`.
   Verify: поля `model_id`, `base`, `global_score`, `by_role`, `by_task_type`,
   `consecutive_fails`, `tickets` — все присутствуют в `ModelScore.to_dict()`.

2. Прочитать `src/planfoldr/knowledge_base.py` — убедиться, что `to_dict()` хранит `content`,
   `read_roles`, `write_roles` (не только `versions`).
   Verify: открыть `kb.json` из любого run — убедиться, что `content` в словаре.

3. Прочитать `src/planfoldr/cli.py` — понять текущую структуру argparse для правильной
   вставки новых аргументов.
   Verify: `grep -n "argparse\|add_argument" src/planfoldr/cli.py`.

### Implementation
4. В `src/planfoldr/score.py` добавить статический метод `ScoreSystem.from_dict(d, *, audit=None)`,
   реализованный по схеме из Части A.
   Verify: unit-тест: `ss.to_dict()` → `from_dict(ss.to_dict())` → `ss2.combined(...)` совпадает.

5. В `src/planfoldr/knowledge_base.py` добавить статический метод `KnowledgeBase.from_dict(d, *, audit=None)`.
   Verify: unit-тест: `kb.to_dict()` → `from_dict(kb.to_dict())` → контент секций совпадает.

6. В `src/planfoldr/orchestrator.py` в `Orchestrator.__init__` добавить параметры
   `seed_scores: Optional[Path] = None` и `seed_kb: Optional[Path] = None`.
   При их наличии — заменить `ScoreSystem(self.audit)` и `KnowledgeBase(self.audit)` на
   соответствующие `from_dict()` загрузки.
   Verify: тест: создать run с scored модели, сохранить `scores.json`, загрузить в новый
   `Orchestrator(seed_scores=...)`, убедиться что `score.scores` не пуст и `combined(...)` > 0.

7. В `src/planfoldr/cli.py` добавить `--seed-scores` и `--seed-kb` аргументы, передать в
   `Orchestrator(...)`.
   Verify: `python -m planfoldr run scenario.yaml --help` показывает `--seed-scores` и `--seed-kb`.

### Verification
8. Запустить полный тестовый набор:
   ```bash
   .venv/bin/python -m pytest -q
   ```
   Verify: 0 FAILED, 0 ERROR.

9. Написать тест `tests/test_cross_run_persistence.py`:
   - Запустить Orchestrator с StubModel → сохранить `scores.json` и `kb.json`
   - Создать второй Orchestrator с `seed_scores=` и `seed_kb=` → убедиться, что модели
     уже имеют ненулевые скоры, KB содержит секции из первого запуска.
   Verify: тест зелёный.

## Final Verification

- `.venv/bin/python -m pytest -q` → 0 FAILED.
- `grep -n "from_dict" src/planfoldr/score.py` → вхождение `ScoreSystem.from_dict`.
- `grep -n "from_dict" src/planfoldr/knowledge_base.py` → вхождение `KnowledgeBase.from_dict`.
- `grep -n "seed_scores\|seed_kb" src/planfoldr/orchestrator.py` → вхождения в `__init__`.
- `python -m planfoldr run --help` показывает `--seed-scores`, `--seed-kb`.
