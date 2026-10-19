'''UI module for Lumi Maze game.
Implements GameUI using Ursina 8.3.0 entities.
All UI elements are created, updated, and destroyed without external assets.
Redesigned for 1280x720 child-friendly warm high-contrast HUD.
'''

from ursina import Entity, Text, Button, camera, color, destroy

class GameUI:
    """Manages all UI screens: menu, HUD, result, pause.
    All methods are idempotent – they reuse existing entities when possible.
    """

    def __init__(self):
        self.menu_entities = []
        self.hud_entities = {}
        self.result_entities = []
        self.pause_entity = None
        self._initialized = True

    # ---------------------------------------------------------------------
    # Utility helpers
    # ---------------------------------------------------------------------
    def _safe_destroy(self, obj):
        try:
            if obj is not None:
                destroy(obj)
        except Exception:
            pass

    def clear(self):
        for e in self.menu_entities:
            self._safe_destroy(e)
        self.menu_entities.clear()
        for key, e in list(self.hud_entities.items()):
            self._safe_destroy(e)
        self.hud_entities.clear()
        for e in self.result_entities:
            self._safe_destroy(e)
        self.result_entities.clear()
        self._safe_destroy(self.pause_entity)
        self.pause_entity = None

    # ---------------------------------------------------------------------
    # Menu screen
    # ---------------------------------------------------------------------
    def show_menu(self, on_start):
        self.clear()
        # Warm light card behind contents (centered, compact)
        card = Entity(
            model='quad',
            parent=camera.ui,
            position=(0, 0, .1),
            scale=(0.95, 0.90),
            color=color.rgb32(250, 240, 220),
            collider=None,
        )
        self.menu_entities.append(card)

        title = Text(
            'Луми и Лабиринты',
            parent=camera.ui,
            origin=(0, 0),
            position=(0, 0.28),
            scale=2.0,
            color=color.rgb32(220, 130, 40),
            background=False,
        )
        desc = Text(
            'Собирай фрукты и найди выход из лабиринта.\n'
            'Здесь нет ловушек — только помощники!\n\n'
            'WASD / стрелки — движение\n'
            'Esc / P — пауза    R — повтор    M — меню',
            parent=camera.ui,
            origin=(0, 0),
            position=(0, 0.02),
            scale=1.05,
            color=color.rgb32(60, 45, 30),
            background=False,
        )
        btn_timed = Button(
            text='На время',
            parent=camera.ui,
            color=color.rgb32(230, 160, 70),
            scale=(0.42, 0.1),
            position=(0, -0.22),
            on_click=lambda: on_start('timed'),
        )
        btn_easy = Button(
            text='Лёгкий',
            parent=camera.ui,
            color=color.rgb32(130, 180, 100),
            scale=(0.42, 0.1),
            position=(0, -0.38),
            on_click=lambda: on_start('easy'),
        )
        self.menu_entities.extend([title, desc, btn_timed, btn_easy])

    # ---------------------------------------------------------------------
    # HUD – called every frame
    # ---------------------------------------------------------------------
    def show_hud(self, level, mode, time_left, total_score, freeze_left, speed_factor, hint=''):
        if not self.hud_entities:
            self.clear()
            # Compact warm header card (centered, height ~65px, translucent)
            self.hud_entities['card'] = Entity(
                model='quad',
                parent=camera.ui,
                position=(0, 0.455),
                scale=(1.65, 0.09),
                color=color.rgba32(248, 239, 220, 218),
                collider=None,
            )
            # Level / mode (left, increased scale for readability)
            self.hud_entities['level'] = Text(
                parent=camera.ui,
                origin=(0, 0),
                position=(-0.66, 0.455),
                scale=1.05,
                color=color.rgb32(60, 40, 20),
                background=False,
            )
            # Score (center, increased scale for readability)
            self.hud_entities['score'] = Text(
                parent=camera.ui,
                origin=(0, 0),
                position=(0, 0.455),
                scale=1.05,
                color=color.rgb32(60, 40, 20),
                background=False,
            )
            # Time / infinity (right, increased scale for readability)
            self.hud_entities['time'] = Text(
                parent=camera.ui,
                origin=(0, 0),
                position=(0.72, 0.455),
                scale=1.05,
                color=color.rgb32(60, 40, 20),
                background=False,
            )
            # Freeze status (left lower, only when active, badge style)
            self.hud_entities['freeze'] = Text(
                parent=camera.ui,
                origin=(0, 0),
                position=(-0.72, 0.38),
                scale=0.8,
                color=color.rgb32(140, 30, 30),
                background=False,
            )
            # Speed status (right lower, only when active, badge style)
            self.hud_entities['speed'] = Text(
                parent=camera.ui,
                origin=(0, 0),
                position=(0.72, 0.38),
                scale=0.8,
                color=color.rgb32(140, 100, 30),
                background=False,
            )
            # Hint at bottom (dark translucent card, only when non-empty)
            self.hud_entities['hint_card'] = Entity(
                model='quad',
                parent=camera.ui,
                position=(0, -0.42),
                scale=(1.6, 0.08),
                color=color.rgba32(40, 30, 20, 180),
                collider=None,
                enabled=False,
            )
            self.hud_entities['hint'] = Text(
                parent=camera.ui,
                origin=(0, 0),
                position=(0, -0.42),
                scale=0.9,
                color=color.rgb32(240, 230, 200),
                background=False,
            )

        # Text updates
        mode_name = 'На время' if mode == 'timed' else 'Без времени'
        self.hud_entities['level'].text = f"Уровень: {level}  •  {mode_name}"
        self.hud_entities['score'].text = f"Счёт: {total_score}"
        if mode == 'easy':
            time_text = '∞'
        else:
            time_text = f"Время: {max(0, int(time_left))} с"
        self.hud_entities['time'].text = time_text

        # Freeze / speed only when active (badge style)
        if freeze_left > 0.05:
            self.hud_entities['freeze'].text = f"Заморозка: {freeze_left:.0f} с"
            self.hud_entities['freeze'].enabled = True
        else:
            self.hud_entities['freeze'].text = ''
            self.hud_entities['freeze'].enabled = False

        if abs(speed_factor - 1.0) > 0.01:
            self.hud_entities['speed'].text = f"Скорость: {speed_factor:.2f}×"
            self.hud_entities['speed'].enabled = True
        else:
            self.hud_entities['speed'].text = ''
            self.hud_entities['speed'].enabled = False

        # Hint card visibility and text
        if hint:
            self.hud_entities['hint'].text = hint
            self.hud_entities['hint_card'].enabled = True
        else:
            self.hud_entities['hint'].text = ''
            self.hud_entities['hint_card'].enabled = False

    # ---------------------------------------------------------------------
    # Result screen
    # ---------------------------------------------------------------------
    def show_result(self, won, level, route_points, fruit_points, total_score, final, on_next, on_retry, on_menu):
        self.clear()
        card = Entity(
            model='quad',
            parent=camera.ui,
            position=(0, 0, .1),
            scale=(0.95, 0.90),
            color=color.rgb32(250, 240, 220),
            collider=None,
        )
        self.result_entities.append(card)

        title_text = (
            'Победа в кампании!' if (won and final)
            else ('Победа!' if won else 'Не получилось')
        )
        title = Text(
            title_text,
            parent=camera.ui,
            origin=(0, 0),
            position=(0, 0.28),
            scale=2.0,
            color=color.rgb32(50, 140, 60) if won else color.rgb32(180, 55, 40),
            background=False,
        )
        self.result_entities.append(title)

        # Auto-advance message for win below final level
        auto_msg = ''
        if won and not final:
            auto_msg = 'Следующий уровень через 2 секунды'

        details_lines = [
            f"Уровень: {level}",
            f"Баллы за путь: {route_points}",
            f"Баллы за фрукты: {fruit_points}",
            f"Итого: {total_score}",
        ]
        if auto_msg:
            details_lines.append(auto_msg)
        details = '\n'.join(details_lines)

        detail_txt = Text(
            details,
            parent=camera.ui,
            origin=(0, 0),
            position=(0, 0.02),
            scale=1.15,
            color=color.rgb32(60, 45, 30),
            background=False,
        )
        self.result_entities.append(detail_txt)

        btn_y = -0.22
        buttons = []
        if won and not final:
            btn_next = Button(
                text='Следующий',
                parent=camera.ui,
                color=color.rgb32(230, 160, 70),
                scale=(0.36, 0.09),
                position=(0, btn_y),
                on_click=lambda: on_next(),
            )
            buttons.append(btn_next)
            btn_y -= 0.12
        if not won:
            btn_retry = Button(
                text='Повторить',
                parent=camera.ui,
                color=color.rgb32(230, 140, 60),
                scale=(0.36, 0.09),
                position=(0, btn_y),
                on_click=lambda: on_retry(),
            )
            buttons.append(btn_retry)
            btn_y -= 0.12
        btn_menu = Button(
            text='Меню',
            parent=camera.ui,
            color=color.rgb32(130, 180, 100),
            scale=(0.36, 0.09),
            position=(0, btn_y),
            on_click=lambda: on_menu(),
        )
        buttons.append(btn_menu)
        self.result_entities.extend(buttons)

    # ---------------------------------------------------------------------
    # Pause overlay
    # ---------------------------------------------------------------------
    def show_pause(self, paused):
        if paused:
            if self.pause_entity is None:
                parent = Entity(parent=camera.ui)
                overlay = Entity(
                    parent=parent,
                    model='quad',
                    scale=(1.28, 0.72),
                    color=color.rgba32(30, 20, 10, 166),
                    collider=None,
                )
                txt = Text(
                    'Пауза',
                    parent=parent,
                    origin=(0, 0),
                    position=(0, 0.05),
                    scale=2.2,
                    color=color.rgb32(250, 240, 220),
                    background=False,
                )
                sub = Text(
                    'Нажмите Esc или P для продолжения',
                    parent=parent,
                    origin=(0, 0),
                    position=(0, -0.15),
                    scale=0.75,
                    color=color.rgb32(230, 220, 200),
                    background=False,
                )
                self.pause_entity = parent
            else:
                self.pause_entity.enabled = True
        else:
            if self.pause_entity is not None:
                self.pause_entity.enabled = False
