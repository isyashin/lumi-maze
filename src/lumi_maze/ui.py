'''UI module for Lumi Maze game.
Implements GameUI using Ursina 8.3.0 entities.
All UI elements are created, updated, and destroyed without external assets.
''' 

from ursina import Entity, Text, Button, camera, color, destroy

class GameUI:
    """Manages all UI screens: menu, HUD, result, pause.
    All methods are idempotent – they reuse existing entities when possible.
    """

    def __init__(self):
        # Containers for different UI groups
        self.menu_entities = []
        self.hud_entities = {}
        self.result_entities = []
        self.pause_entity = None
        self._initialized = True

    # ---------------------------------------------------------------------
    # Utility helpers
    # ---------------------------------------------------------------------
    def _safe_destroy(self, obj):
        """Destroy an Ursina entity if it exists and hasn't been destroyed yet."""
        try:
            if obj is not None:
                destroy(obj)
        except Exception:
            # Entity may already be destroyed – ignore
            pass

    def clear(self):
        """Remove *all* UI entities owned by this GameUI.
        Safe to call multiple times.
        """
        # Menu
        for e in self.menu_entities:
            self._safe_destroy(e)
        self.menu_entities.clear()
        # HUD – keep dict keys but destroy values
        for key, e in self.hud_entities.items():
            self._safe_destroy(e)
        self.hud_entities.clear()
        # Result
        for e in self.result_entities:
            self._safe_destroy(e)
        self.result_entities.clear()
        # Pause overlay
        self._safe_destroy(self.pause_entity)
        self.pause_entity = None

    # ---------------------------------------------------------------------
    # Menu screen
    # ---------------------------------------------------------------------
    def show_menu(self, on_start):
        """Display the main menu.
        `on_start` is a callable that receives a mode string ('timed' or 'easy').
        """
        # Clean any existing UI
        self.clear()

        # Centered card behind menu contents
        menu_card = Entity(
            model='quad',
            parent=camera.ui,
            position=(0, 0),
            scale=(0.85, 0.85),
            color=color.rgba(0, 0, 0.35, 0.85),
            collider=None,
        )
        self.menu_entities.append(menu_card)

        # Title
        title = Text(
            "Луми и Лабиринты",
            parent=camera.ui,
            origin=(0,0),
            position=(0, 0.25),
            scale=2,
            color=color.orange,
            background=False,
        )
        # Short description / controls
        desc = Text(
            "Управляй Луми, собирай фрукты, избегай ловушек.\n" 
            "Клавиши: WASD/стрелки – движение, Esc/P – пауза, R – повтор, M – меню.\n" 
            "Цель: пройти все уровни.",
            parent=camera.ui,
            origin=(0,0),
            position=(0, 0.05),
            scale=1,
            color=color.white,
            background=False,
        )
        # Buttons
        btn_timed = Button(
            text='Начать (Таймер)',
            parent=camera.ui,
            color=color.azure,
            scale=(0.4,0.1),
            position=(0, -0.15),
            on_click=lambda: on_start('timed')
        )
        btn_easy = Button(
            text='Начать (Лёгкий)',
            parent=camera.ui,
            color=color.lime,
            scale=(0.4,0.1),
            position=(0, -0.30),
            on_click=lambda: on_start('easy')
        )
        self.menu_entities.extend([title, desc, btn_timed, btn_easy])

    # ---------------------------------------------------------------------
    # HUD – called every frame
    # ---------------------------------------------------------------------
    def show_hud(self, level, mode, time_left, total_score, freeze_left, speed_factor, hint=''):
        """Update (or create) the heads‑up display.
        `mode` is 'easy' or 'timed'. For easy mode time displays as ∞.
        """
        # Ensure HUD entities exist; if not, create them once.
        if not self.hud_entities:
            # Clear any leftover menu, result or pause UI before first HUD creation
            self.clear()
            # Top strip behind HUD text rows
            self.hud_entities['strip'] = Entity(
                model='quad',
                parent=camera.ui,
                position=(0, 0.36),
                scale=(1.2, 0.2),
                color=color.rgba(0, 0, 0.35, 0.85),
                collider=None,
            )
            # Level / mode
            self.hud_entities['level'] = Text(
                parent=camera.ui,
                origin=(0,0),
                position=(-0.58, 0.42),
                scale=0.7,
                color=color.yellow,
            )
            # Time left
            self.hud_entities['time'] = Text(
                parent=camera.ui,
                origin=(0,0),
                position=(0.58, 0.42),
                scale=0.7,
                color=color.cyan,
            )
            # Score
            self.hud_entities['score'] = Text(
                parent=camera.ui,
                origin=(0,0),
                position=(-0.58, 0.3),
                scale=0.7,
                color=color.lime,
            )
            # Freeze left
            self.hud_entities['freeze'] = Text(
                parent=camera.ui,
                origin=(0,0),
                position=(0, 0.3),
                scale=0.7,
                color=color.violet,
            )
            # Speed factor
            self.hud_entities['speed'] = Text(
                parent=camera.ui,
                origin=(0,0),
                position=(0.58, 0.3),
                scale=0.7,
                color=color.orange,
            )
            # Hint line at bottom
            self.hud_entities['hint'] = Text(
                parent=camera.ui,
                origin=(0,0),
                position=(0, -0.45),
                scale=0.6,
                color=color.white,
            )
        # Update texts
        mode_name = 'На время' if mode == 'timed' else 'Без времени'
        self.hud_entities['level'].text = f"Уровень: {level}   Режим: {mode_name}"
        if mode == 'easy':
            time_display = '∞'
        else:
            time_display = f"Время: {int(time_left)} с"
        self.hud_entities['time'].text = time_display
        self.hud_entities['score'].text = f"Счёт: {total_score}"
        self.hud_entities['freeze'].text = f"Заморозка: {freeze_left:.1f} с"
        self.hud_entities['speed'].text = f"Скорость: {speed_factor:.2f} x"
        self.hud_entities['hint'].text = hint

    # ---------------------------------------------------------------------
    # Result screen
    # ---------------------------------------------------------------------
    def show_result(self, won, level, route_points, fruit_points, total_score, final, on_next, on_retry, on_menu):
        """Display the level result.
        `won` – bool, whether player succeeded.
        `final` – bool, true if this was the final campaign level.
        Callbacks receive no arguments.
        """
        self.clear()
        # Centered card behind result contents
        result_card = Entity(
            model='quad',
            parent=camera.ui,
            position=(0, 0),
            scale=(0.85, 0.85),
            color=color.rgba(0, 0, 0.35, 0.85),
            collider=None,
        )
        self.result_entities.append(result_card)

        # Main result text
        result_text = "Победа в кампании!" if (won and final) else ("Победа!" if won else "Поражение")
        title = Text(
            result_text,
            parent=camera.ui,
            origin=(0,0),
            position=(0, 0.25),
            scale=2,
            color=color.lime if won else color.red,
        )
        # Details
        details = (
            f"Уровень: {level}\n"
            f"Баллы за путь: {route_points}\n"
            f"Баллы за фрукты: {fruit_points}\n"
            f"Итого: {total_score}"
        )
        detail_txt = Text(
            details,
            parent=camera.ui,
            origin=(0,0),
            position=(0, 0.0),
            scale=1,
            color=color.white,
        )
        btn_y = -0.25
        buttons = []
        if won and not final:
            btn_next = Button(
                text='Следующий уровень',
                parent=camera.ui,
                color=color.azure,
                scale=(0.35,0.08),
                position=(0, btn_y),
                on_click=lambda: on_next()
            )
            buttons.append(btn_next)
            btn_y -= 0.12
        if not won:
            btn_retry = Button(
                text='Повторить',
                parent=camera.ui,
                color=color.orange,
                scale=(0.35,0.08),
                position=(0, btn_y),
                on_click=lambda: on_retry()
            )
            buttons.append(btn_retry)
            btn_y -= 0.12
        # Menu button always present
        btn_menu = Button(
            text='Меню',
            parent=camera.ui,
            color=color.lime,
            scale=(0.35,0.08),
            position=(0, btn_y),
            on_click=lambda: on_menu()
        )
        buttons.append(btn_menu)
        self.result_entities.extend([title, detail_txt] + buttons)

    # ---------------------------------------------------------------------
    # Pause overlay
    # ---------------------------------------------------------------------
    def show_pause(self, paused):
        """Toggle pause overlay while keeping HUD visible.
        """
        if paused:
            if self.pause_entity is None:
                overlay = Entity(
                    parent=camera.ui,
                    model='quad',
                    scale=(1.28, 0.72),  # slightly larger than 1280x720 aspect
                    color=color.rgba(0,0,0,0.6),
                )
                txt = Text(
                    'Пауза',
                    parent=camera.ui,
                    origin=(0,0),
                    position=(0,0),
                    scale=2,
                    color=color.white,
                )
                self.pause_entity = Entity(parent=camera.ui)
                overlay.parent = self.pause_entity
                txt.parent = self.pause_entity
            else:
                # already exists – just ensure it's visible
                self.pause_entity.enabled = True
        else:
            if self.pause_entity:
                self.pause_entity.enabled = False
