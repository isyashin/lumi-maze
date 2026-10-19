# Готовые ассеты игры

Проверено 19.10.2026. В репозиторий включены только файлы, которые используются игрой. Все перечисленные страницы разрешают свободное использование по CC0; для материалов OpenGameArt с несколькими лицензиями выбран вариант CC0. Перед добавлением нового файла проверяйте лицензию на странице автора, сохраняйте исходную ссылку и проверяйте вид в собранной игре.

| Что используется | Источник и лицензия | Файлы в `src/lumi_maze/assets` |
| --- | --- | --- |
| Анимированный лисёнок Луми | [Quaternius Ultimate Animated Animals](https://quaternius.com/packs/ultimateanimatedanimals.html), CC0. Отдельный glTF получен через [зеркало PixelTriks](https://www.pixeltriks.com/browse?pack=quaternius-ultimate-animated-animals), когда официальный архив не скачивался из-за квоты хранилища. | `quaternius_fox.gltf` |
| Деревья, кусты, камни, грибы и цветы | [Kenney Nature Kit](https://kenney.nl/assets/nature-kit), CC0. Из полного набора взяты 9 GLB. | `nature/*.glb` |
| Яблоко и клубника | [Kenney Food Kit](https://kenney.nl/assets/food-kit), CC0. Модели используют общую карту цветов. | `food/apple.glb`, `food/strawberry.glb`, `food/Textures/colormap.png` |
| Каменные покрытия и песок | [MELLE, handpainted stone-texture](https://opengameart.org/content/handpainted-stone-texture) и [handpainted stone way-texture](https://opengameart.org/content/handpainted-stone-way-texture), CC0. | `textures/oldstone.png`, `crystal.png`, `underwater.png`, `dirt.png`, `path.png` |
| Лесная кладка и пол пещеры | [PamNawi, HandpaintedStone Wall Texture](https://opengameart.org/content/handpaintedstone-wall-texture-handpaintedwall2png) и [Handpainted Stone Tile Textures](https://opengameart.org/content/handpainted-stone-tile-textures), CC0 / CC BY 4.0 на страницах автора. | `textures/paintwall.png`, `floor.png` |

Текстуры по темам: камень — песчаная дорожка и тёплая кладка; лес — каменистая дорожка с травой и замшелая кирпичная стена; пещера — серые плиты и светлая кристальная кладка; ручьи — песчаная дорожка и сине-зелёная кладка. Пол и стены всегда берутся из разных файлов.

Лисёнок использует клипы `Idle`, `Gallop`, `Eating`, `Gallop_Jump`. Время воспроизведения согласовано с движением между клетками. Panda3D Actor и glTF-модели получают шейдер сцены с приоритетом 10, иначе под родительским Ursina Entity их материалы становятся белыми. `build.ps1` включает каталог `assets` и модули загрузчика в папку Windows-сборки.

Также просмотрены [KayKit Forest Nature Pack](https://kaylousberg.itch.io/kaykit-forest), [Quaternius Stylized Nature MegaKit](https://quaternius.com/packs/stylizednaturemegakit.html) и [Kenney Modular Dungeon Kit](https://kenney.nl/assets/modular-dungeon-kit). Они не входят в текущую сборку: первый в пробе выглядел слишком геометричным, второй требует отбора моделей и проверки в игре, третий в пробе дал холодную палитру. Оценка кандидатов и следующего визуального прохода — в [ASSET_RESEARCH.md](ASSET_RESEARCH.md).
