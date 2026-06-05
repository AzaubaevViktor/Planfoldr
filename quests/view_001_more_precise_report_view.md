нужно сделать следующие исправления:

Проблема в том, что я вижу по логам ollama, что процесс идёт, и по логам в stream.jsonl тоже вижу, что процесс идёт, но в report.html нет ещё ни одной выполненной таски, что нелогично, ведь до запуска модели что-то уже должно было случиться.
Плюс я хочу видеть структуру циклов прямо на страничке, сейчас её нет
Для каждой таски я хочу видеть доступный ей контекст, input, output, прямо в таблице, по умолчанию всё скрытое.
Мне нужны все шаги — создание файлов, кто это создание запросил, остатки бюджета на каждом шагу итд
Мне нужна МАКСИМАЛЬНАЯ ПРОЗРАЧНОСТЬ с возможностью скрывать часть неинтересных данных
И надо не просто сырую json-ку показывать в html report, а чтобы можно было прочитать и воспринять. И должно быть понимание откуда пришёл запрос и куда ушёл запрос

То есть как это должно выглядеть:
```
Starting `ollama_cli_todo_app_demo`
cut with additional human-readable info

cycle_name: prev_task -> [active task] -> next task
command: command args in cwd
cut with additional human-readable info about execution process
result: success (reason)
short diff (X files changed, Y delted, +200 lines -100)
cut with additional diff info

cycle_name: prev_task -> [active task] -> next task
command: command args in cwd
cut with additional human-readable info about execution process
result: success (reason)
short diff (X files changed, Y delted, +200 lines -100)
cut with additional diff info

cycle_name: prev_task -> [active task] -> next task
model: goal with X НУ
cut with additional human readable info about model message (if it works now, with generated part of text)
result: failure (wrong format)

retry 1/3 with additional message to model
cut with additional message

cycle_name: prev_task -> [active task] -> next task
model: goal with X НУ with retry info
cut with additional human readable info about model message (if it works now, with generated part of text)
result: success

cycle up/down to new_cycle_name

...

```

Человек должен суметь это прочитать, воспринять, а главное, отладить.
Брать это нужно из структуры репорта из report_001