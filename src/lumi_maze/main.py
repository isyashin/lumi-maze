"""Main application for Lumi Maze.

Entry point: python -m lumi_maze.main [--smoke OUTPUT.png]
"""

from __future__ import annotations

import sys
import argparse
import math
import shutil
from pathlib import Path
from typing import Optional, Callable

from ursina import (
    Ursina, Entity, Vec3, Vec2, camera, window, color, time,
    held_keys, destroy, application, Sky, DirectionalLight, AmbientLight, invoke
)

from .core import generate_level, Maze, Cell
from .rules import RunState
from .avatar import Fox, prepare_avatar_rendering
from .world import WorldView, CELL_SIZE
from .ui import GameUI


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720

# Camera defaults
CAMERA_OFFSET = (0, 5.5, -8.5)
CAMERA_FOV = 60
CAM_DISTANCE = 12.0
CAM_HEIGHT = 7.0
CAM_LOOK_OFFSET_Y = 0.7
CAM_SMOOTH = 12.0

# Overview camera for trampoline
OVERVIEW_DURATION = 3.0
OVERVIEW_RISE_TIME = 0.5
OVERVIEW_HOLD_TIME = 1.5

# Movement animation
MOVE_DURATION = 0.36  # constant-speed travel across one cell
ARRIVAL_LOCK_DURATION = 0.65  # short fruit-eating pause before the next move

# Per-theme scene colours: (sky, sun, ambient) as RGB tuples.
THEME_LIGHTING = {
    'stone': ((75, 165, 230), (255, 236, 198), (37, 39, 42)),
    'forest': ((76, 159, 202), (255, 240, 206), (35, 42, 33)),
    'cave': ((35, 48, 78), (151, 175, 228), (29, 31, 42)),
    'streams': ((73, 174, 225), (237, 246, 229), (31, 41, 44)),
}

# Heading mapping: (dx, dz) -> degrees (0 = +Z, 90 = +X)
HEADING_MAP = {
    (1, 0): 90.0,   # +X (east)
    (-1, 0): 270.0, # -X (west)
    (0, 1): 0.0,    # +Z (north)
    (0, -1): 180.0, # -Z (south)
}


# ---------------------------------------------------------------------------
# Main Game Controller
# ---------------------------------------------------------------------------
class Game(Entity):
    """Main gameplay controller managing state, entities, camera, and input."""

    def __init__(self, app: Ursina, ui: GameUI) -> None:
        super().__init__()
        self.app = app
        self.ui = ui

        # Campaign state
        self.mode: str = 'timed'
        self.campaign_seed: Optional[int] = None
        self.current_level: int = 1
        self.total_score: int = 0

        # Level entities
        self.maze: Optional[Maze] = None
        self.world_view: Optional[WorldView] = None
        self.run_state: Optional[RunState] = None
        self.fox: Optional[Fox] = None
        self.sky = None
        self.sun = None
        self.ambient = None

        # Camera
        self.cam_target = Entity()  # follows fox smoothly
        self.cam_target_pos = Vec3(0, 0, 0)
        self.cam_overview_active = False
        self.cam_overview_timer = 0.0
        self.cam_overview_phase = 0  # 0=rise, 1=hold, 2=return
        self.cam_prev_distance = CAM_DISTANCE
        self.cam_prev_height = CAM_HEIGHT
        self.cam_overview_start_pos = Vec3(0, 0, 0)
        self.cam_overview_start_rot = Vec3(0, 0, 0)

        # Trampoline jump and overview state
        self.overview_pending = 0.0

        # Movement animation
        self.move_active = False
        self.move_timer = 0.0
        self.move_from = Vec3(0, 0, 0)
        self.move_to = Vec3(0, 0, 0)
        self.move_target_cell: Optional[Cell] = None
        self.last_move_dir: Optional[tuple[int, int]] = None
        # Item collected by try_move, shown/removed only when the fox arrives.
        self.pending_item: Optional[tuple[Cell, str]] = None
        self.arrival_lock_timer = 0.0

        # Input handling
        self.paused = False
        self.result_showing = False
        self.last_hint = ''
        self.hint_timer = 0.0
        self._result_handled = False  # guard against duplicate win/loss

        # Setup scene lighting/sky
        self._setup_scene()

    def _setup_scene(self) -> None:
        """Create sky, lights, and camera parent."""
        prepare_avatar_rendering()
        # Cheerful storybook sky (recoloured per theme on level load)
        self.sky = Sky(color=color.rgb32(75, 165, 230))

        # Warm sun with real shadows.  The color argument of DirectionalLight
        # is swallowed in this Ursina version, so assign it afterwards.
        self.sun = DirectionalLight(
            shadows=True,
            rotation=(52, -38, 0),
            shadow_map_resolution=Vec2(2048, 2048),
        )
        self.sun.color = color.rgb32(255, 236, 198)
        # Light defaults overwrite the constructor rotation, so set it again.
        self.sun.rotation = (42, -35, 0)
        # Soft cool-blue ambient fill keeps the fox readable in shade.
        self.ambient = AmbientLight(color=color.rgb32(98, 112, 132))

        # Camera follows cam_target
        camera.parent = self.cam_target
        camera.position = CAMERA_OFFSET
        camera.look_at(self.cam_target.position)
        camera.rotation_z = 0
        camera.fov = CAMERA_FOV

    def input(self, key: str) -> None:
        """Handle key press events via Ursina's entity input system."""
        self._on_key(key)

    # -----------------------------------------------------------------------
    # Campaign / Level management
    # -----------------------------------------------------------------------
    def start_new_campaign(self, mode: str, seed: Optional[int] = None) -> None:
        """Start a fresh campaign with new seed."""
        self.mode = mode
        self.campaign_seed = seed if seed is not None else (int(time.time() * 1000) & 0xFFFFFFFF)
        self.current_level = 1
        self.total_score = 0
        self.paused = False
        self.result_showing = False
        self.last_hint = ''
        self.hint_timer = 0.0
        self._result_handled = False
        self._reset_movement_state()
        self.cam_overview_active = False
        self._load_level(self.current_level)

    def retry_level(self) -> None:
        """Retry current level with same seed."""
        if self.campaign_seed is not None:
            # If current level was won, don't award points twice
            if self.run_state and self.run_state.status == 'won':
                self.total_score -= self.run_state.level_points
            self.paused = False
            self.result_showing = False
            self.last_hint = ''
            self.hint_timer = 0.0
            self._result_handled = False
            self._reset_movement_state()
            self.cam_overview_active = False
            self._load_level(self.current_level)

    def next_level(self) -> None:
        """Advance to next level (only if won and level < 7)."""
        if self.current_level < 7:
            self.current_level += 1
            self.paused = False
            self.result_showing = False
            self.last_hint = ''
            self.hint_timer = 0.0
            self._result_handled = False
            self._reset_movement_state()
            self.cam_overview_active = False
            self._load_level(self.current_level)
        else:
            # Final level won - stay on level 7 with result showing; menu button works
            pass

    def return_to_menu(self) -> None:
        """Clean up level and show main menu."""
        self._cleanup_level()
        self.campaign_seed = None
        self.current_level = 1
        self.total_score = 0
        self.paused = False
        self.result_showing = False
        self.last_hint = ''
        self.hint_timer = 0.0
        self._result_handled = False
        self._reset_movement_state()
        self.cam_overview_active = False
        self.ui.show_menu(lambda m: self.start_new_campaign(m))

    def _load_level(self, level: int) -> None:
        """Generate and load a level."""
        assert self.campaign_seed is not None
        self._cleanup_level()

        self.maze = generate_level(level, self.campaign_seed)
        self.run_state = RunState(self.maze, self.mode)  # type: ignore[arg-type]
        self.world_view = WorldView(self.maze)

        # Create fox at start position
        start_x, start_z = self.maze.start
        start_pos = Vec3(start_x * CELL_SIZE, 0, start_z * CELL_SIZE)
        self.fox = Fox(position=start_pos)

        # Recolour the existing sky and lights for this location.  No new
        # lights are created, so retries do not accumulate them.
        sky_rgb, sun_rgb, ambient_rgb = THEME_LIGHTING.get(
            self.maze.theme, THEME_LIGHTING['stone']
        )
        if self.sky:
            self.sky.color = color.rgb32(*sky_rgb)
        if self.sun:
            self.sun.color = color.rgb32(*sun_rgb)
        if self.ambient:
            self.ambient.color = color.rgb32(*ambient_rgb)

        # Fit shadow bounds to the freshly generated geometry on every reload.
        if self.sun and self.world_view:
            self.sun.update_bounds(self.world_view.root)

        # Camera target starts at fox
        self.cam_target.position = start_pos + Vec3(0, CAM_LOOK_OFFSET_Y, 0)
        self.cam_target_pos = Vec3(self.cam_target.position)

        # Reset camera to normal view
        self._reset_camera()

        # Settle the new world's cutaway before the first frame is drawn.
        # WallBatch clamps dt to 0.1 and CUTAWAY_TIME is 0.15, so two calls
        # converge immediately; later frames keep animating smoothly.
        self.world_view.update_visibility(
            camera.world_position, self.fox.world_position, 0.1
        )
        self.world_view.update_visibility(
            camera.world_position, self.fox.world_position, 0.1
        )

        # Show HUD
        self._update_hud()

    def _cleanup_level(self) -> None:
        """Destroy level entities."""
        if self.world_view:
            self.world_view.clear()
            self.world_view = None
        if self.fox:
            destroy(self.fox)
            self.fox = None
        self.run_state = None
        self.maze = None
        self._reset_movement_state()
        self.cam_overview_active = False

    def _reset_movement_state(self) -> None:
        """Cancel interpolation and any pickup that has not arrived yet."""
        self.move_active = False
        self.move_timer = 0.0
        self.move_target_cell = None
        self.last_move_dir = None
        self.pending_item = None
        self.arrival_lock_timer = 0.0
        self.overview_pending = 0.0

    # -----------------------------------------------------------------------
    # Camera
    # -----------------------------------------------------------------------
    def _reset_camera(self) -> None:
        """Return camera to normal third-person follow."""
        # Better third-person pose: offset from cam_target, looking slightly down and ahead
        camera.position = CAMERA_OFFSET
        camera.fov = CAMERA_FOV
        # Since camera is parented to cam_target, look_at uses world coordinates
        if self.cam_target:
            camera.look_at(self.cam_target.position)
        camera.rotation_z = 0
        self.cam_overview_active = False

    def _start_overview(self) -> None:
        """Start trampoline overview: lift camera high overhead from current pose."""
        self.cam_overview_active = True
        self.cam_overview_timer = 0.0
        self.cam_overview_phase = 0
        # Store complete current local camera pose for smooth return
        self.cam_overview_start_pos = Vec3(camera.position)
        self.cam_overview_start_rot = Vec3(camera.rotation_x, camera.rotation_y, camera.rotation_z)

    def _update_camera(self, dt: float) -> None:
        """Smooth camera follow and overview transition."""
        if not self.fox or not self.run_state:
            return

        # Always update cam_target to follow fox horizontally (even during overview)
        fox_pos = self.fox.position
        target_pos = Vec3(fox_pos.x, CAM_LOOK_OFFSET_Y + self.fox.actor.getY(), fox_pos.z)

        # Smooth follow (clamp interpolation factor to avoid overshoot)
        smooth_factor = min(1.0, CAM_SMOOTH * dt)
        self.cam_target_pos = Vec3(
            self.cam_target_pos.x + (target_pos.x - self.cam_target_pos.x) * smooth_factor,
            self.cam_target_pos.y + (target_pos.y - self.cam_target_pos.y) * smooth_factor,
            self.cam_target_pos.z + (target_pos.z - self.cam_target_pos.z) * smooth_factor
        )
        self.cam_target.position = self.cam_target_pos

        if self.world_view:
            self.world_view.update_visibility(
                camera.world_position, self.fox.world_position, dt
            )

        if self.cam_overview_active:
            self.cam_overview_timer += dt

            # Calculate overview height based on maze size (sufficient for 19x19)
            maze_size = max(self.maze.width, self.maze.height) if self.maze else 10
            overview_height = max(maze_size * CELL_SIZE * 0.7, 40.0)

            if self.cam_overview_phase == 0:  # Rise smoothly from stored pose
                rise_duration = OVERVIEW_RISE_TIME
                t = min(self.cam_overview_timer / rise_duration, 1.0)
                eased = t * t * (3 - 2 * t)

                # Interpolate from stored local pose to overhead pose
                # Overhead: position (0, overview_height, 0), rotation (90, 0, 0) in local space
                camera.position = Vec3(
                    self.cam_overview_start_pos.x + (0 - self.cam_overview_start_pos.x) * eased,
                    self.cam_overview_start_pos.y + (overview_height - self.cam_overview_start_pos.y) * eased,
                    self.cam_overview_start_pos.z + (0 - self.cam_overview_start_pos.z) * eased
                )
                camera.look_at(self.cam_target.position)
                camera.rotation_z = 0

                if t >= 1.0:
                    self.cam_overview_phase = 1
                    self.cam_overview_timer = 0.0

            elif self.cam_overview_phase == 1:  # Hold high
                hold_duration = OVERVIEW_HOLD_TIME
                camera.position = Vec3(0, overview_height, 0)
                camera.look_at(self.cam_target.position)
                camera.rotation_z = 0

                if self.cam_overview_timer >= hold_duration:
                    self.cam_overview_phase = 2
                    self.cam_overview_timer = 0.0

            elif self.cam_overview_phase == 2:  # Return smoothly to stored pose
                return_duration = OVERVIEW_DURATION - OVERVIEW_RISE_TIME - OVERVIEW_HOLD_TIME
                t = min(self.cam_overview_timer / return_duration, 1.0)
                eased = t * t * (3 - 2 * t)

                camera.position = Vec3(
                    0 + (self.cam_overview_start_pos.x - 0) * eased,
                    overview_height + (self.cam_overview_start_pos.y - overview_height) * eased,
                    0 + (self.cam_overview_start_pos.z - 0) * eased
                )
                camera.look_at(self.cam_target.position)
                camera.rotation_z = 0

                if t >= 1.0:
                    self.cam_overview_active = False
                    # Restore exact stored pose
                    camera.position = self.cam_overview_start_pos
                    camera.rotation_x = self.cam_overview_start_rot.x
                    camera.rotation_y = self.cam_overview_start_rot.y
                    # Re-establish look_at for normal follow
                    camera.look_at(self.cam_target.position)
                    camera.rotation_z = 0
            return

    # -----------------------------------------------------------------------
    # Movement & Input
    # -----------------------------------------------------------------------
    def _on_key(self, key: str) -> None:
        """Handle key press events."""
        # Global keys that work anytime
        if key == 'escape' or key == 'p':
            self._toggle_pause()
            return

        if key == 'm':
            self.return_to_menu()
            return

        if key == 'r':
            self.retry_level()
            return

        if key == 'enter' and self.result_showing:
            # Enter on result screen: advance if won, retry if lost
            if self.run_state and self.run_state.status == 'won':
                self.next_level()
            else:
                self.retry_level()
            return

        if self.paused or self.result_showing or not self.run_state:
            return

        # Movement keys (single press)
        move_dir = self._key_to_dir(key)
        if move_dir:
            self._try_start_move(move_dir)

    def _key_to_dir(self, key: str) -> Optional[tuple[int, int]]:
        """Map key to (dx, dz)."""
        if key in ('w', 'up arrow'):
            return (0, 1)
        if key in ('s', 'down arrow'):
            return (0, -1)
        if key in ('d', 'right arrow'):
            return (1, 0)
        if key in ('a', 'left arrow'):
            return (-1, 0)
        return None

    def _held_move_dir(self) -> Optional[tuple[int, int]]:
        """Return the first movement direction currently held, if any."""
        for key in ('w', 'up arrow', 's', 'down arrow',
                    'd', 'right arrow', 'a', 'left arrow'):
            if held_keys.get(key, 0):
                return self._key_to_dir(key)
        return None

    def _try_start_move(self, dir_vec: tuple[int, int]) -> bool:
        """Attempt to start a move to an adjacent cell."""
        if (self.move_active or self.arrival_lock_timer > 0 or self.overview_pending > 0 or self.cam_overview_active or (self.fox and self.fox._jumping)
                or not self.run_state or not self.fox):
            return False

        cx, cz = self.run_state.cell
        dx, dz = dir_vec
        target = (cx + dx, cz + dz)

        # One validated rules transition per cell.
        collected_item = self.run_state.try_move(target)
        if self.run_state.cell != target:
            # Move rejected (wall or not playing); no extra steps.
            return False

        # Move accepted - start constant-speed animation.
        self.move_active = True
        self.move_timer = 0.0
        self.move_from = Vec3(self.fox.position)
        self.move_to = Vec3(target[0] * CELL_SIZE, 0, target[1] * CELL_SIZE)
        self.move_target_cell = target
        self.last_move_dir = dir_vec
        # Keep the world item visible; it is consumed on arrival.
        self.pending_item = (target, collected_item) if collected_item else None

        # Update fox heading (the fox turns smoothly towards it).
        heading = HEADING_MAP.get(dir_vec, 0)
        self.fox.set_walking(True, heading)

        # Update HUD immediately for timer/freeze/speed changes
        self._update_hud()
        return True

    def _on_item_collected(self, cell: Cell, item: str) -> None:
        """Handle item collection: remove from world, show hint, and celebrate pickup."""
        if self.world_view:
            self.world_view.remove_item(cell)

        # Russian hints
        hints = {
            'apple': 'Яблоко: таймер заморожен на 10 с' if self.mode == 'timed' else 'Яблоко: +150 очков',
            'strawberry': 'Клубника: таймер в 2 раза медленнее' if self.mode == 'timed' else 'Клубника: +150 очков',
            'trampoline': 'Батут: обзор лабиринта сверху',
        }
        self.last_hint = hints.get(item, '')
        self.hint_timer = 3.0  # show for 3 seconds

        if item in ('apple', 'strawberry'):
            # Match the eating clip: no new cell while the fox eats.
            self.arrival_lock_timer = ARRIVAL_LOCK_DURATION

        if item in ('apple', 'strawberry') and self.fox:
            self.fox.celebrate_pickup()
            if self.world_view:
                tint = color.rgb32(255, 190, 65) if item == 'apple' else color.rgb32(255, 90, 140)
                center = Vec3(cell[0] * CELL_SIZE, 0.65, cell[1] * CELL_SIZE)
                for i in range(5):
                    angle = i * math.tau / 5
                    particle = Entity(
                        parent=self.world_view.root,
                        model='sphere',
                        color=tint,
                        scale=0.15,
                        position=center,
                    )
                    particle.animate_position(
                        center + Vec3(math.cos(angle) * 0.6, 0.6, math.sin(angle) * 0.6),
                        duration=0.65,
                    )
                    particle.animate_scale(0, duration=0.65)
                    invoke(destroy, particle, delay=0.7)

        if item == 'trampoline':
            if self.fox:
                self.fox.jump()
            self.overview_pending = 0.8

    def _continue_after_arrival(self) -> None:
        """Start a held-key follow-up cell or settle back to Idle."""
        if not self.fox or not self.run_state:
            return
        if (self.run_state.status != 'playing' or self.arrival_lock_timer > 0 or self.overview_pending > 0 or self.cam_overview_active or self.fox._jumping):
            self.fox.set_walking(False, self.fox.heading)
            return
        dir_vec = self._held_move_dir()
        if dir_vec and self._try_start_move(dir_vec):
            # Same-frame continuation keeps Gallop running across the boundary.
            return
        self.fox.set_walking(False, self.fox.heading)

    def _update_movement(self, dt: float) -> None:
        """Animate fox movement between cells at constant horizontal speed."""
        if not self.move_active or not self.fox:
            return

        self.move_timer += dt
        t = min(self.move_timer / MOVE_DURATION, 1.0)

        self.fox.position = Vec3(
            self.move_from.x + (self.move_to.x - self.move_from.x) * t,
            0,
            self.move_from.z + (self.move_to.z - self.move_from.z) * t
        )

        if t >= 1.0:
            # Land exactly on the validated cell centre before any pickup FX.
            self.fox.position = Vec3(self.move_to)
            arrived_cell = self.move_target_cell
            self.move_active = False
            self.move_target_cell = None

            pending = self.pending_item
            self.pending_item = None
            if pending and arrived_cell is not None and pending[0] == arrived_cell:
                self._on_item_collected(arrived_cell, pending[1])

            # Check win/loss after move completes
            self._check_win_loss()
            self._continue_after_arrival()

    def _check_win_loss(self) -> None:
        """Check if level won or lost after move completes."""
        if not self.run_state or self._result_handled:
            return

        if self.run_state.status == 'won':
            self._result_handled = True
            self._on_level_won()
        elif self.run_state.status == 'lost':
            self._result_handled = True
            self._on_level_lost()

    def _on_level_won(self) -> None:
        """Handle level win."""
        assert self.run_state
        self.result_showing = True

        route_points = self.run_state.level_points - self.run_state.fruit_points
        fruit_points = self.run_state.fruit_points
        self.total_score += self.run_state.level_points

        final = (self.current_level == 7)

        def on_next():
            self.result_showing = False
            self.next_level()

        def on_retry():
            self.result_showing = False
            self.retry_level()

        def on_menu():
            self.result_showing = False
            self.return_to_menu()

        won_level = self.current_level
        won_run = self.run_state
        def delayed_next():
            if (self.result_showing and self.current_level == won_level
                    and self.run_state is won_run and won_run.status == 'won'):
                self.next_level()

        # Auto-advance for levels 1-6 after 1.8 seconds
        if not final:
            invoke(delayed_next, delay=1.8)

        self.ui.show_result(
            won=True,
            level=self.current_level,
            route_points=route_points,
            fruit_points=fruit_points,
            total_score=self.total_score,
            final=final,
            on_next=on_next,
            on_retry=on_retry,
            on_menu=on_menu,
        )

    def _on_level_lost(self) -> None:
        """Handle level loss (time out)."""
        self.result_showing = True

        def on_retry():
            self.result_showing = False
            self.retry_level()

        def on_menu():
            self.result_showing = False
            self.return_to_menu()

        self.ui.show_result(
            won=False,
            level=self.current_level,
            route_points=0,
            fruit_points=0,
            total_score=self.total_score,
            final=False,
            on_next=lambda: None,  # not used for loss
            on_retry=on_retry,
            on_menu=on_menu,
        )

    def _toggle_pause(self) -> None:
        """Toggle pause state."""
        if self.result_showing:
            return
        self.paused = not self.paused
        self.ui.show_pause(self.paused)

    # -----------------------------------------------------------------------
    # HUD
    # -----------------------------------------------------------------------
    def _update_hud(self) -> None:
        """Update HUD with current state."""
        if not self.run_state or self.result_showing:
            return

        freeze_left = self.run_state.freeze_left
        speed_factor = self.run_state.speed_factor
        time_left = self.run_state.time_left

        self.ui.show_hud(
            level=self.current_level,
            mode=self.mode,
            time_left=time_left,
            total_score=self.total_score + self.run_state.level_points,
            freeze_left=freeze_left,
            speed_factor=speed_factor,
            hint=self.last_hint if self.hint_timer > 0 else '',
        )

    # -----------------------------------------------------------------------
    # Main update loop (called by Ursina as Entity.update)
    # -----------------------------------------------------------------------
    def update(self) -> None:
        """Main per-frame update."""
        dt_raw = time.dt
        if dt_raw < 0:
            dt_raw = 0.0
        # Use raw dt for game logic (timer, hint, overview) so low FPS doesn't slow the game
        dt_logic = dt_raw
        # Clamp dt for visual interpolation/animation only
        dt_visual = min(dt_raw, 0.1)

        # Hint timer (real-time)
        if self.hint_timer > 0:
            self.hint_timer -= dt_logic
            if self.hint_timer <= 0:
                self.last_hint = ''
                self._update_hud()

        # Pause: stop game logic but keep UI responsive
        if self.paused:
            return

        if self.result_showing or not self.run_state:
            if self.fox:
                self.fox.update_animation(dt_visual)
            if self.world_view:
                self.world_view.update(dt_visual)
            self._update_camera(dt_visual)
            return

        # Game logic tick (real-time)
        self.run_state.tick(dt_logic)

        # Check for timer loss while standing still (not moving)
        if self.run_state.status == 'lost' and not self.move_active and not self._result_handled:
            self._result_handled = True
            self._on_level_lost()
            return

        # Arrival celebration lock counts down in real time.
        if self.arrival_lock_timer > 0:
            self.arrival_lock_timer = max(0.0, self.arrival_lock_timer - dt_logic)

        # Handle held_keys for continuous movement
        if (not self.move_active and self.arrival_lock_timer <= 0
                and self.run_state.status == 'playing'):
            dir_vec = self._held_move_dir()
            if dir_vec:
                self._try_start_move(dir_vec)

        # Update animations (visual)
        if self.fox:
            self.fox.update_animation(dt_visual)
        if self.world_view:
            self.world_view.update(dt_visual)

        # Camera (visual)
        self._update_camera(dt_logic if self.cam_overview_active else dt_visual)

        # Handle overview pending countdown
        if self.overview_pending > 0:
            self.overview_pending -= dt_logic
            if self.overview_pending <= 0:
                self.overview_pending = 0.0
                self._start_overview()

        # Movement animation (visual)
        self._update_movement(dt_visual)

        # HUD
        self._update_hud()


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------
def run_smoke(output_path: str) -> int:
    """Run smoke test: load level 1 via Game, render, save PNG."""
    import os

    # Use a relative ASCII filename for Panda3D screenshot
    temp_filename = 'lumi-smoke.png'
    temp_path = Path(temp_filename)

    # Remove any existing temp file from previous runs
    if temp_path.exists():
        try:
            temp_path.unlink()
        except Exception:
            pass

    # Track success of THIS run only
    smoke_success = False

    # Create app with offscreen rendering
    app = Ursina(
        title='Lumi Maze Smoke',
        borderless=False,
        fullscreen=False,
        size=(WINDOW_WIDTH, WINDOW_HEIGHT),
        development_mode=False,
    )

    # Keep UI rendering for HUD (GameUI)
    window.render_ui = True

    # Create Game and UI (reuses normal game setup: sky, lights, camera)
    ui = GameUI()
    game = Game(app, ui)

    # Start deterministic timed level 1 with fixed seed
    game.start_new_campaign('timed', seed=42)

    # Ensure HUD is showing
    game._update_hud()

    def delayed_screenshot():
        nonlocal smoke_success
        try:
            # Force a render
            app.graphicsEngine.render_frame()

            # Get screenshot using Panda3D's base.screenshot to relative ASCII name
            application.base.screenshot(namePrefix=temp_filename, defaultFilename=False)

            # Check if file was created and nonempty
            if temp_path.exists() and temp_path.stat().st_size > 0:
                # Move/copy to requested output path (which may be Unicode)
                target_path = Path(output_path)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(temp_path), str(target_path))
                print(f"Screenshot saved to {output_path}")
                smoke_success = True
                application.quit()
                return
            else:
                print("Failed to capture screenshot")
        except Exception as e:
            print(f"Screenshot error: {e}")

        application.quit()

    class _SmokeScreenshotTrigger(Entity):
        """Fire the smoke screenshot after a minimum number of update frames."""

        def __init__(self, callback: Callable[[], None], min_frames: int = 30) -> None:
            super().__init__()
            self._callback = callback
            self._frames_left = min_frames
            self._fired = False

        def update(self) -> None:
            if self._fired:
                return
            self._frames_left -= 1
            if self._frames_left <= 0:
                # Disable before capturing so no later frame can fire again.
                self._fired = True
                self.disable()
                self._callback()

    # Wait for real update frames (shader load included) instead of wall time.
    _screenshot_trigger = _SmokeScreenshotTrigger(delayed_screenshot)

    app.run()

    # Return 0 only if THIS run successfully saved a nonempty PNG
    if smoke_success:
        return 0
    return 1


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Луми и Лабиринты')
    parser.add_argument('--smoke', metavar='OUTPUT.png', help='Run smoke test and save screenshot')
    args = parser.parse_args(argv)

    if args.smoke:
        return run_smoke(args.smoke)

    # Normal game
    app = Ursina(
        title='Луми и Лабиринты',
        borderless=False,
        fullscreen=False,
        size=(WINDOW_WIDTH, WINDOW_HEIGHT),
        development_mode=False,
        vsync=True,
    )

    window.exit_button.visible = False
    window.fps_counter.enabled = False

    ui = GameUI()
    game = Game(app, ui)

    # Start with menu
    ui.show_menu(lambda m: game.start_new_campaign(m))

    app.run()
    return 0


if __name__ == '__main__':
    sys.exit(main())
