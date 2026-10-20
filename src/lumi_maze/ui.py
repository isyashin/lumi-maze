"""Storybook-style screens for Lumi Maze.

The UI is deliberately self-contained: it only creates entities below
``camera.ui`` and never imports the game rules or the level view.  Panels use
rounded procedural quads, the menu backdrop is shipped with the package, and
HUD labels are cached so the per-frame update does no entity creation.
"""

from pathlib import Path

from ursina import Button, Entity, Text, Texture, camera, color, destroy
from ursina.models.procedural.quad import Quad


_MENU_BACKDROP = (
    Path(__file__).resolve().parent / 'assets' / 'ui' / 'menu_backdrop.png'
)

# Forest-teal surfaces with warm, low-saturation accents.
DARK_CARD = color.rgba32(18, 42, 43, 238)
DARK_DEEP = color.rgba32(8, 24, 25, 216)
HUD_CARD = color.rgba32(21, 48, 48, 233)
HUD_INNER = color.rgba32(30, 65, 61, 232)
SUMMARY_PANEL = color.rgba32(30, 63, 60, 190)
CREAM = color.rgb32(248, 240, 218)
CREAM_DIM = color.rgb32(204, 213, 191)
GOLD = color.rgb32(246, 191, 94)
AMBER = color.rgb32(231, 161, 64)
AMBER_HOVER = color.rgb32(247, 181, 84)
AMBER_PRESSED = color.rgb32(202, 134, 45)
MINT = color.rgb32(137, 199, 161)
MINT_HOVER = color.rgb32(160, 218, 180)
MINT_PRESSED = color.rgb32(113, 171, 136)
INK = color.rgb32(24, 43, 40)
WARM_RED = color.rgb32(238, 118, 96)
PEACH = color.rgb32(240, 191, 154)
SHADOW = color.rgba32(3, 14, 15, 108)
OVERLAY = color.rgba32(5, 17, 19, 206)
HAIRLINE = color.rgba32(255, 255, 255, 30)


class GameUI:
    """Manage the menu, HUD, result and pause screens.

    ``clear()`` is safe to call repeatedly.  Menu/result overlays are rebuilt
    when shown, while HUD entities are built once and then only updated.
    """

    def __init__(self):
        self.menu_entities = []
        self.hud_entities = {}
        self.hud_root = None
        self.result_entities = []
        self.pause_entities = []
        self.pause_entity = None

        self._menu_texture = None
        self._hud_cache = {}
        self._hud_enabled = {}
        self._pause_overlay = None

    # ------------------------------------------------------------------
    # Small construction helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _aspect():
        try:
            value = float(camera.aspect_ratio)
            if value > 0:
                return value
        except Exception:
            pass
        return 16.0 / 9.0

    @staticmethod
    def _rounded(width, height, radius=.08):
        aspect = width / height if height else 1.0
        return Quad(radius=radius, segments=8, aspect=aspect)

    def _panel(
        self,
        x,
        y,
        width,
        height,
        color_value,
        z=.1,
        radius=.08,
        parent=None,
    ):
        return Entity(
            parent=parent if parent is not None else camera.ui,
            model=self._rounded(width, height, radius),
            position=(x, y, z),
            scale=(width, height, 1),
            color=color_value,
            collider=None,
        )

    def _text(
        self,
        content,
        x,
        y,
        scale=1.0,
        color_value=CREAM,
        origin=(0, 0),
        z=0.0,
        parent=None,
    ):
        return Text(
            content,
            parent=parent if parent is not None else camera.ui,
            origin=origin,
            position=(x, y, z),
            scale=scale,
            color=color_value,
        )

    def _button(
        self,
        label,
        x,
        y,
        width,
        height,
        primary,
        on_click,
        text_size=1.1,
    ):
        base = AMBER if primary else MINT
        hover = AMBER_HOVER if primary else MINT_HOVER
        pressed = AMBER_PRESSED if primary else MINT_PRESSED
        button = Button(
            text=label,
            parent=camera.ui,
            position=(x, y, 0),
            scale=(width, height),
            color=base,
            highlight_color=hover,
            pressed_color=pressed,
            text_color=INK,
            text_size=text_size,
            radius=.12,
            on_click=on_click,
        )
        return button

    def _safe_destroy(self, obj):
        try:
            if obj is not None:
                destroy(obj)
        except Exception:
            pass

    def clear(self):
        """Destroy only entities created by this GameUI instance."""
        for entity in self.menu_entities:
            self._safe_destroy(entity)
        self.menu_entities.clear()

        for entity in self.hud_entities.values():
            self._safe_destroy(entity)
        self.hud_entities.clear()
        self._safe_destroy(self.hud_root)
        self.hud_root = None
        self._hud_cache.clear()
        self._hud_enabled.clear()

        for entity in self.result_entities:
            self._safe_destroy(entity)
        self.result_entities.clear()

        for entity in reversed(self.pause_entities):
            self._safe_destroy(entity)
        self.pause_entities.clear()
        self.pause_entity = None
        self._pause_overlay = None

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------
    def show_menu(self, on_start):
        self.clear()
        aspect = self._aspect()

        # Full-screen painted forest scene; the fox occupies the right half.
        if _MENU_BACKDROP.exists():
            if self._menu_texture is None:
                self._menu_texture = Texture(str(_MENU_BACKDROP))
            background = Entity(
                parent=camera.ui,
                model='quad',
                position=(0, 0, .3),
                scale=(aspect, 1, 1),
                texture=self._menu_texture,
                color=color.rgb32(255, 255, 255),
                collider=None,
            )
        else:
            background = Entity(
                parent=camera.ui,
                model='quad',
                position=(0, 0, .3),
                scale=(aspect, 1, 1),
                color=DARK_DEEP,
                collider=None,
            )
        self.menu_entities.append(background)

        # Left-half storybook card, with real margins on both 16:9 and 4:3.
        card_width = min(.72, aspect * .44)
        card_height = .86
        card_x = -aspect / 4.0
        self.menu_entities.append(
            self._panel(
                card_x + .012, -.012, card_width, card_height, SHADOW, z=.12,
            )
        )
        self.menu_entities.append(
            self._panel(card_x, 0, card_width, card_height, DARK_CARD, z=.1),
        )

        self.menu_entities.append(
            self._text('Луми', card_x, .295, 2.9, GOLD),
        )
        self.menu_entities.append(
            self._text(
                'Лабиринты и приключения', card_x, .207, 1.12, CREAM,
            ),
        )
        self.menu_entities.append(
            self._panel(card_x, .168, .13, .006, AMBER, z=.1, radius=.5),
        )
        self.menu_entities.append(
            self._text('Найди путь домой', card_x, .125, .94, CREAM_DIM),
        )

        button_width = min(.56, card_width - .12)
        self.menu_entities.append(
            self._button(
                'На время',
                card_x,
                .018,
                button_width,
                .098,
                True,
                lambda: on_start('timed'),
            ),
        )
        self.menu_entities.append(
            self._button(
                'Без времени',
                card_x,
                -.102,
                button_width,
                .098,
                False,
                lambda: on_start('easy'),
            ),
        )

        inner_left = card_x - card_width / 2 + .062
        inner_right = card_x + card_width / 2 - .062
        dot_x = inner_left + .008
        text_x = inner_left + .038

        legend_rows = (
            (-.236, AMBER, 'Яблоко — замораживает время'),
            (-.277, color.rgb32(224, 125, 134), 'Клубника — замедляет таймер'),
            (-.318, MINT, 'Батут — показывает лабиринт'),
        )
        for y, dot_color, label in legend_rows:
            self.menu_entities.append(
                Entity(
                    parent=camera.ui,
                    model=Quad(radius=.5, segments=6, aspect=1),
                    position=(dot_x, y, 0),
                    scale=(.016, .016, 1),
                    color=dot_color,
                    collider=None,
                ),
            )
            self.menu_entities.append(
                self._text(label, text_x, y, .72, CREAM_DIM, origin=(-.5, 0)),
            )

        self.menu_entities.append(
            self._panel(
                card_x, -.357, card_width - .12, .003, HAIRLINE,
                z=.1, radius=.5,
            ),
        )
        self.menu_entities.append(
            self._text(
                'WASD / стрелки — движение',
                inner_left, -.396, .61, CREAM_DIM, origin=(-.5, 0),
            ),
        )
        self.menu_entities.append(
            self._text(
                'Esc — пауза',
                inner_right, -.396, .61, CREAM_DIM, origin=(.5, 0),
            ),
        )

    # ------------------------------------------------------------------
    # HUD
    # ------------------------------------------------------------------
    def _build_hud(self):
        aspect = self._aspect()
        margin = max(.035, aspect * .02)
        gap = .025
        card_width = min(.44, (aspect - 2 * margin - 2 * gap) / 3.0)
        total_width = 3 * card_width + 2 * gap
        left_x = -total_width / 2 + card_width / 2
        middle_x = 0.0
        right_x = total_width / 2 - card_width / 2
        card_height = .10
        card_y = .431

        self.hud_root = Entity(parent=camera.ui)
        root = self.hud_root

        self.hud_entities['left_shadow'] = self._panel(
            left_x + .006, card_y - .006, card_width, card_height,
            SHADOW, z=.12, parent=root,
        )
        self.hud_entities['middle_shadow'] = self._panel(
            middle_x + .006, card_y - .006, card_width, card_height,
            SHADOW, z=.12, parent=root,
        )
        self.hud_entities['right_shadow'] = self._panel(
            right_x + .006, card_y - .006, card_width, card_height,
            SHADOW, z=.12, parent=root,
        )

        for key, x in (
            ('left_card', left_x),
            ('middle_card', middle_x),
            ('right_card', right_x),
        ):
            self.hud_entities[key] = self._panel(
                x, card_y, card_width, card_height, HUD_CARD,
                z=.1, radius=.10, parent=root,
            )

        label_y = card_y + .020
        value_y = card_y - .012
        sub_y = card_y - .039

        self.hud_entities['level_label'] = self._text(
            'УРОВЕНЬ', left_x, label_y, .56, CREAM_DIM, parent=root,
        )
        self.hud_entities['level_value'] = self._text(
            '1 / 7', left_x, value_y, 1.20, GOLD, parent=root,
        )
        self.hud_entities['mode_value'] = self._text(
            'НА ВРЕМЯ', left_x, sub_y, .50, CREAM_DIM, parent=root,
        )

        self.hud_entities['score_label'] = self._text(
            'СЧЁТ', middle_x, label_y, .56, CREAM_DIM, parent=root,
        )
        self.hud_entities['score_value'] = self._text(
            '0', middle_x, value_y - .003, 1.38, GOLD, parent=root,
        )

        self.hud_entities['time_label'] = self._text(
            'ВРЕМЯ', right_x, label_y, .56, CREAM_DIM, parent=root,
        )
        self.hud_entities['time_value'] = self._text(
            '∞', right_x, value_y, 1.30, GOLD, parent=root,
        )
        self.hud_entities['time_sub'] = self._text(
            'Без времени', right_x, sub_y, .50, CREAM_DIM, parent=root,
        )

        # Effect badges are pre-built, then shown/hidden without new entities.
        badge_width = .31
        badge_height = .047
        badge_y = .349
        freeze_x = left_x
        speed_x = left_x + badge_width + gap

        self.hud_entities['freeze_card'] = self._panel(
            freeze_x, badge_y, badge_width, badge_height, HUD_INNER,
            z=.1, radius=.10, parent=root,
        )
        self.hud_entities['freeze_text'] = self._text(
            '', freeze_x, badge_y, .55, CREAM, parent=root,
        )
        self.hud_entities['speed_card'] = self._panel(
            speed_x, badge_y, badge_width, badge_height, HUD_INNER,
            z=.1, radius=.10, parent=root,
        )
        self.hud_entities['speed_text'] = self._text(
            '', speed_x, badge_y, .55, CREAM, parent=root,
        )
        for key in ('freeze_card', 'freeze_text', 'speed_card', 'speed_text'):
            self.hud_entities[key].enabled = False

        hint_width = min(aspect - .12, 1.48)
        hint_y = -.438
        self.hud_entities['hint_card'] = self._panel(
            0, hint_y, hint_width, .064, DARK_DEEP,
            z=.1, radius=.10, parent=root,
        )
        self.hud_entities['hint_text'] = self._text(
            '', 0, hint_y, .70, CREAM, parent=root,
        )
        self.hud_entities['hint_card'].enabled = False
        self.hud_entities['hint_text'].enabled = False

        self._hud_enabled = {
            'freeze': False,
            'speed': False,
            'hint': False,
        }

    def _hud_text(self, key, value):
        if self._hud_cache.get(key) != value:
            self.hud_entities[key].text = value
            self._hud_cache[key] = value

    def _hud_pair_visible(self, key, active):
        if self._hud_enabled.get(key) == active:
            return
        self._hud_enabled[key] = active
        self.hud_entities[key + '_card'].enabled = active
        self.hud_entities[key + '_text'].enabled = active

    def show_hud(
        self,
        level,
        mode,
        time_left,
        total_score,
        freeze_left,
        speed_factor,
        hint='',
    ):
        if not self.hud_entities:
            self.clear()
            self._build_hud()

        easy = mode == 'easy'
        self._hud_text('level_value', f'{level} / 7')
        self._hud_text('mode_value', 'БЕЗ ВРЕМЕНИ' if easy else 'НА ВРЕМЯ')
        self._hud_text('score_value', str(int(total_score)))

        if easy:
            time_text = '∞'
            time_sub = 'Без времени'
        else:
            seconds = max(0, int(time_left))
            if seconds >= 60:
                time_text = f'{seconds // 60}:{seconds % 60:02d}'
            else:
                time_text = f'{seconds} с'
            time_sub = 'осталось'
        self._hud_text('time_value', time_text)
        self._hud_text('time_sub', time_sub)

        warning = (not easy) and time_left < 15
        if self._hud_cache.get('time_warning') != warning:
            self.hud_entities['time_value'].color = WARM_RED if warning else GOLD
            self._hud_cache['time_warning'] = warning

        freeze_active = freeze_left > .05
        if freeze_active:
            self._hud_text(
                'freeze_text', f'Пауза времени: {max(0, int(freeze_left))} с',
            )
        self._hud_pair_visible('freeze', freeze_active)

        speed_active = abs(speed_factor - 1.0) > .01
        if speed_active:
            speed_text = f'{speed_factor:.2f}'.rstrip('0').rstrip('.')
            self._hud_text(
                'speed_text', 'Таймер ×' + speed_text.replace('.', ','),
            )
        self._hud_pair_visible('speed', speed_active)

        hint_active = bool(hint)
        if hint_active:
            self._hud_text('hint_text', hint)
        self._hud_pair_visible('hint', hint_active)

    # ------------------------------------------------------------------
    # Result
    # ------------------------------------------------------------------
    def show_result(
        self,
        won,
        level,
        route_points,
        fruit_points,
        total_score,
        final,
        on_next,
        on_retry,
        on_menu,
    ):
        self.clear()
        aspect = self._aspect()

        self.result_entities.append(
            Entity(
                parent=camera.ui,
                model='quad',
                position=(0, 0, .3),
                scale=(aspect, 1, 1),
                color=OVERLAY,
                collider=None,
            ),
        )

        card_width = min(.82, aspect - .16)
        card_height = .82
        self.result_entities.append(
            self._panel(
                .012, -.012, card_width, card_height, SHADOW, z=.12,
            ),
        )
        self.result_entities.append(
            self._panel(0, 0, card_width, card_height, DARK_CARD, z=.1),
        )

        if won and final:
            title = 'Приключение пройдено!'
            title_scale = 1.78
            subtitle = 'Все семь лабиринтов позади'
        elif won:
            title = 'Отличный путь!'
            title_scale = 2.15
            subtitle = f'Уровень {level} из 7'
        else:
            title = 'Попробуем ещё?'
            title_scale = 2.02
            subtitle = f'Уровень {level} из 7'

        self.result_entities.append(
            self._text(
                title, 0, .323, title_scale,
                GOLD if won else PEACH,
            ),
        )
        self.result_entities.append(
            self._text(subtitle, 0, .251, .68, CREAM_DIM),
        )

        summary_width = min(card_width - .16, .63)
        summary_height = .255
        summary_y = .073
        self.result_entities.append(
            self._panel(
                0, summary_y, summary_width, summary_height,
                SUMMARY_PANEL, z=.1, radius=.10,
            ),
        )

        row_left = -summary_width / 2 + .055
        row_right = summary_width / 2 - .055
        rows = (
            ('Маршрут', str(int(route_points)), .155),
            ('Фрукты', str(int(fruit_points)), .104),
        )
        for label, value, y in rows:
            self.result_entities.append(
                self._text(
                    label, row_left, y, .70, CREAM_DIM, origin=(-.5, 0),
                ),
            )
            self.result_entities.append(
                self._text(
                    value, row_right, y, .84, CREAM, origin=(.5, 0),
                ),
            )

        self.result_entities.append(
            self._panel(
                0, .070, summary_width - .10, .003, HAIRLINE,
                z=.1, radius=.5,
            ),
        )
        self.result_entities.append(
            self._text(
                'Итого', row_left, .018, .66, CREAM_DIM, origin=(-.5, 0),
            ),
        )
        self.result_entities.append(
            self._text(
                str(int(total_score)), row_right, .010, 1.55, GOLD,
                origin=(.5, 0),
            ),
        )

        if won and not final:
            self.result_entities.append(
                self._text(
                    'Следующий уровень...', 0, -.118, .68, GOLD,
                ),
            )

        button_width = .275
        button_height = .090
        button_y = -.312
        if won and not final:
            self.result_entities.append(
                self._button(
                    'Дальше', -.155, button_y, button_width, button_height,
                    True, lambda: on_next(), text_size=1.0,
                ),
            )
            self.result_entities.append(
                self._button(
                    'В меню', .155, button_y, button_width, button_height,
                    False, lambda: on_menu(), text_size=1.0,
                ),
            )
        elif not won:
            self.result_entities.append(
                self._button(
                    'Ещё раз', -.155, button_y, button_width, button_height,
                    True, lambda: on_retry(), text_size=1.0,
                ),
            )
            self.result_entities.append(
                self._button(
                    'В меню', .155, button_y, button_width, button_height,
                    False, lambda: on_menu(), text_size=1.0,
                ),
            )
        else:
            self.result_entities.append(
                self._button(
                    'В меню', 0, button_y, .33, button_height,
                    False, lambda: on_menu(), text_size=1.05,
                ),
            )

    # ------------------------------------------------------------------
    # Pause
    # ------------------------------------------------------------------
    def _build_pause(self):
        aspect = self._aspect()
        root = Entity(parent=camera.ui)
        self.pause_entities.append(root)
        self.pause_entity = root

        overlay = Entity(
            parent=root,
            model='quad',
            position=(0, 0, .3),
            scale=(aspect, 1, 1),
            color=OVERLAY,
            collider=None,
        )
        self.pause_entities.append(overlay)
        self._pause_overlay = overlay

        card_width = min(.46, aspect - .24)
        card_height = .30
        self.pause_entities.append(
            self._panel(
                .010, -.010, card_width, card_height, SHADOW,
                z=.12, parent=root,
            ),
        )
        self.pause_entities.append(
            self._panel(
                0, 0, card_width, card_height, DARK_CARD,
                z=.1, radius=.10, parent=root,
            ),
        )
        self.pause_entities.append(
            self._text('Пауза', 0, .073, 2.18, GOLD, parent=root),
        )
        self.pause_entities.append(
            self._text(
                'Esc или P — продолжить', 0, -.020, .72, CREAM,
                parent=root,
            ),
        )
        self.pause_entities.append(
            self._text(
                'M — вернуться в меню', 0, -.075, .59, CREAM_DIM,
                parent=root,
            ),
        )

    def show_pause(self, paused):
        if paused:
            if self.pause_entity is None:
                self._build_pause()
            else:
                self.pause_entity.enabled = True
                if self._pause_overlay is not None:
                    self._pause_overlay.scale = (self._aspect(), 1, 1)
            if self.hud_root is not None:
                self.hud_root.enabled = False
        else:
            if self.pause_entity is not None:
                self.pause_entity.enabled = False
            if self.hud_root is not None:
                self.hud_root.enabled = True
