# Луми и лабиринты

Трёхмерная игра для Windows. Лисёнок Луми ищет выход из семи процедурных лабиринтов: от небольших каменных руин до леса, пещеры и ручьёв. В новой версии — текстурированный мультяшный лисёнок Pxltiger, высокая камера и полупрозрачные препятствия. Есть режим на время и Easy без отсчёта. Каждый уровень имеет свой лабиринт, а повтор попытки сохраняет его планировку.

## Запуск готовой игры

Последняя проверенная сборка в этой рабочей папке: `dist-cartoon\LumiMaze\LumiMaze.exe`. Для переноса на другой компьютер копируйте **всю папку** `dist-cartoon\LumiMaze`, включая каталог `_internal`. Интернет во время игры не нужен.

Если сборки нет, запустите игру из исходников в PowerShell из этой папки:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_game.py
```

Проверено на Python 3.13.7, Ursina 8.3.0 и Panda3D 1.10.16 под Windows 11.

## Управление и правила

- **WASD или стрелки** — переход между соседними клетками. Удержание клавиши повторяет шаги; сквозь стены пройти нельзя.
- **Esc или P** — пауза; **R** — повтор текущего уровня; **M** — возврат в меню. При победе следующий уровень запускается сам через 1,8 секунды; кнопка «Следующий» или Enter запускает его раньше. После поражения Enter повторяет уровень.
- **Яблоко** останавливает таймер на 10 секунд. **Клубника** замедляет отсчёт вдвое; эффект каждой следующей клубники складывается множителем. **Батут** подбрасывает Луми и на несколько секунд показывает лабиринт сверху.
- В **Easy** таймер отключён, а каждое яблоко и каждая клубника добавляют 150 очков. В обоих режимах очки за выход зависят от длины пройденного маршрута: кратчайший даёт 1000 очков, обходы уменьшают награду.

## Разработка и проверка

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
$env:PYTHONPATH = 'src'
.\.venv\Scripts\python.exe -m pytest -q
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

`build.ps1` использует локальное виртуальное окружение и собирает папку `dist\LumiMaze`. Если предыдущая сборка ещё запущена, используйте `.\build.ps1 -OutputDir dist-cartoon`. Для снимка окна: `.\.venv\Scripts\python.exe run_game.py --smoke screenshots\preview.png`. Готовый `.exe` тоже принимает `--smoke`.

Требования и подробные правила — [docs/PRODUCT.md](docs/PRODUCT.md), устройство модулей — [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), происхождение готовых моделей и текстур — [docs/ASSETS.md](docs/ASSETS.md). Это отдельный Git-репозиторий внутри рабочего пространства GPT-техдира.

## Графика и проверка

Персонаж Fox — Pxltiger, CC BY 4.0; источник, изменения и полный кредит в [CREDITS.txt](CREDITS.txt) и [ASSETS.md](docs/ASSETS.md). Оригиналы выбранных FBX/PNG хранятся в `art-source/pxltiger`, готовый GLB уже включён в игру. Для обычного запуска Blender не нужен.

Проверка полёта/прозрачности в настоящем окне: `$env:PYTHONPATH="src"; .\.venv\Scripts\python.exe tools/qa_feedback.py`. Проверка смены уровней: `tools/qa_lifecycle.py`. Результаты первой пишутся в `.tmp/feedback-qa`. Всего 33 pytest-теста: 21 правило/генерация, 9 проверок формата текстур, 3 проверки скруглённой геометрии.

Восстановление GLB (Blender 4.5.9): `blender --background --factory-startup --python tools/export_pxltiger.py -- art-source/pxltiger src/lumi_maze/assets/pxltiger_fox.glb`. Освещение: `.\.venv\Scripts\python.exe tools/bake_environment.py src/lumi_maze/assets/lighting/daylight.env`. После сборки можно дополнительно скопировать CREDITS.txt рядом с exe; сам NOTICE уже упаковывается в assets.
