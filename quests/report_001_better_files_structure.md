Нужна новая структура report-а:

report.html - файл с человекочитаемым красивым выводом

trace/scenario.json - файл с тем, как шёл сценарий
trace/cycles/cycle_name.json - файлы с тем, как шла работа внутри циклов
trace/tasks/task_type/date_uid/ - информация о запуске таски
trace/tool/tool_name/date_uid/ - информация о запуске тулы
trace/model/model_name/date_uid/ - информация о запуске модели
trace/X/X/X/status.json - текущий статус
trace/X/X/X/context.json - доступный контекст
trace/X/X/X/input.json - входные данные
trace/X/X/X/stream.jsonl - потоковый вывод
trace/X/X/X/assembled.txt - собранный потоковый вывод
trace/X/X/X/content/content_type.txt - конкретный тип контента собранный воедино (например stdout/stderr, или thinking и output для модели)
trace/X/X/X/output.json - то что отдаётся как output

Если текст внутри json-ки больше 1000 символов, внутри json-ки делай строку "$current_file_name_field_full_path.(md/json/txt/...)", и клади рядом артефакт с нужным расширением и типом (если ответ json, то надо класть json, если raw text, то raw_text)

