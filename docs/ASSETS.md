# Готовые ассеты игры

Проверено 20.10.2026. В репозитории сохранены используемые ассеты и ранее испытанные наборы. Все перечисленные страницы разрешают свободное использование по CC0; для материалов OpenGameArt с несколькими лицензиями выбран вариант CC0. Перед добавлением нового файла проверяйте лицензию на странице автора, сохраняйте исходную ссылку и проверяйте вид в собранной игре.

| Что используется | Источник и лицензия | Файлы в `src/lumi_maze/assets` |
| --- | --- | --- |
| Анимированный лисёнок Луми | [Quaternius Ultimate Animated Animals](https://quaternius.com/packs/ultimateanimatedanimals.html), CC0. Отдельный glTF получен через [зеркало PixelTriks](https://www.pixeltriks.com/browse?pack=quaternius-ultimate-animated-animals), когда официальный архив не скачивался из-за квоты хранилища. | `quaternius_fox.gltf` |
| Деревья, кусты, камни, грибы и цветы | [Kenney Nature Kit](https://kenney.nl/assets/nature-kit), CC0. Из полного набора взяты 9 GLB. | `nature/*.glb` |
| Яблоко и клубника | [Kenney Food Kit](https://kenney.nl/assets/food-kit), CC0. Модели используют общую карту цветов. | `food/apple.glb`, `food/strawberry.glb`, `food/Textures/colormap.png` |
| Каменные покрытия и песок | [MELLE, handpainted stone-texture](https://opengameart.org/content/handpainted-stone-texture) и [handpainted stone way-texture](https://opengameart.org/content/handpainted-stone-way-texture), CC0. | `textures/oldstone.png`, `crystal.png`, `underwater.png`, `dirt.png`, `path.png` |
| Лесная кладка и пол пещеры | [PamNawi, HandpaintedStone Wall Texture](https://opengameart.org/content/handpaintedstone-wall-texture-handpaintedwall2png) и [Handpainted Stone Tile Textures](https://opengameart.org/content/handpainted-stone-tile-textures), CC0 / CC BY 4.0 на страницах автора. | `textures/paintwall.png`, `floor.png` |

20.10.2026 для художественного прохода добавлены 12 glTF из бесплатного Standard [Quaternius Stylized Nature MegaKit](https://quaternius.itch.io/stylized-nature-megakit), CC0: `assets/megakit`. Файлы получены из [открытого зеркала](https://github.com/agentkaerf/FreeModels) на commit `db3df04d1e4714298a09510b26fb6de6645138a2`; сохранены `License_Standard.txt` и `provenance.json`. В отдельной сцене проверены загрузка, цвет, габариты и настоящие тени. Также получена [PamNawi Handpainted Grass with Leaves](https://opengameart.org/content/handpainted-grass-with-leaves-2k), CC0: `textures/grasswithleafs.png`. Подключены в игровую сцену: пейзаж, детали проходов и камни пещеры; проверены четыре темы и Windows-сборка.

Текстуры по темам: камень — песчаная дорожка и тёплая кладка; лес — песчаная дорожка и замшелая кирпичная стена; пещера — серые плиты и светлая кристальная кладка; ручьи — песчаная дорожка и сине-зелёная кладка. Пол и стены всегда берутся из разных файлов.

Лисёнок использует клипы `Idle`, `Gallop`, `Eating`, `Gallop_Jump`. Время воспроизведения согласовано с движением между клетками. Panda3D Actor и glTF-модели получают шейдер сцены с приоритетом 10, иначе под родительским Ursina Entity их материалы становятся белыми. `build.ps1` включает каталог `assets` и модули загрузчика в папку Windows-сборки.

Также просмотрены [KayKit Forest Nature Pack](https://kaylousberg.itch.io/kaykit-forest), [Quaternius Stylized Nature MegaKit](https://quaternius.com/packs/stylizednaturemegakit.html) и [Kenney Modular Dungeon Kit](https://kenney.nl/assets/modular-dungeon-kit). KayKit в пробе выглядел слишком геометричным, Modular Dungeon Kit дал холодную палитру. MegaKit после отбора включён в игру. Оценка кандидатов и следующего визуального прохода — в [ASSET_RESEARCH.md](ASSET_RESEARCH.md).

## Производные файлы

20.10.2026 нормали `quaternius_fox.gltf` сглажены утилитой `tools/smooth_fox.py` (порог 75°). Исходник до изменения сохранён в Git commit `401559f`. Независимая проверка подтвердила: изменены только NORMAL-данные (3752 нормали), геометрия, скиннинг и 12 анимаций сохранены. Это смягчает освещение, но не добавляет детализацию силуэта.

`assets/ui/menu_backdrop.png` — рендер этой игры координатором: тот же лисёнок и перечисленные CC0-растения, камни и поверхности. Отдельных сторонних изображений или ограничений лицензии нет.

## Текущий персонаж и трава — 20.10.2026

Игровой Quaternius-лисёнок заменён на [Fox / Toon Fox от Pxltiger](https://sketchfab.com/3d-models/fox-39f97fe58f0b47ce80b6e02814001dd7), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Публичный API автора подтвердил свободное скачивание, лицензию, 30 анимаций и 3450 треугольников; это же число получено из базового FBX. Скачаны базовый FBX, шесть нужных клипов и карты цвета/нормалей/AO из [публичного зеркала](https://github.com/blu-octopus/chicken-chase/tree/b9ae3c074876587282e52e0108715923f5d1143c/Assets/Fox), которое также указывает автора. Выбрана лицензия CC BY со страницы автора, не лицензия Unity Asset Store. Исходники сохранены в art-source/pxltiger; хеши и происхождение — assets/pxltiger/provenance.json, полный кредит/изменения — NOTICE.txt и CREDITS.txt.

Производный assets/pxltiger_fox.glb: Blender 4.5.9 LTS, масштаб меша и rest-костей запечён одинаково, translation-ключи также масштабированы (одного scale родителя недостаточно для текущего Panda-загрузчика). Сохранены Idle, Run, Jump, InAir, Fall, Pickup; встроены две PNG, roughness 0,82. AO скачана как исходник, но в текущий материал не подключена. Переработка не означает одобрение автором игры. Старый Quaternius-файл сохранён как исторический ресурс.

assets/textures/grass_02.png — [rubberduck: handpainted grass texture pack](https://opengameart.org/content/handpainted-grass-texture-pack), CC0, на основе CC0 drummyfish. Выбран непрозрачный бесшовный вариант 1024² без крупных повторяющихся листьев. Исходное изображение не редактировалось.

assets/lighting/daylight.env — численная кубическая карта мягкого дневного света, создаётся tools/bake_environment.py; без сторонней фотографии/HDRI. В ней заранее рассчитаны 9 SH-коэффициентов и отражения; нет тяжёлого расчёта при запуске. Меню заново отрисовано из этой же сцены, с новым персонажем и всеми исходными кредитами.
