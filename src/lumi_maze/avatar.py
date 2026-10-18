"""
Fox avatar for Lumi Maze.

Implements a cute procedural 3D fox using only Ursina built-in primitives.
All animation is done via child entity transforms; no entities are created/destroyed per frame.
"""

from __future__ import annotations

import math
from typing import Final

from ursina import Entity, Vec3, color, time


class Fox(Entity):
    """
    A cute procedural fox avatar.

    The fox is built from Ursina primitives (cubes, spheres, cones) as child entities.
    Animation state is driven by update_animation(dt) and controlled via
    set_walking(active, heading) and jump().

    The root entity's world position is managed externally (by main.py).
    Heading is in degrees, applied to rotation_y.
    """

    # Colours
    ORANGE: Final = color.rgb32(255, 140, 0)
    CREAM: Final = color.rgb32(255, 235, 200)
    DARK: Final = color.rgb32(40, 30, 25)
    NOSE_BLACK: Final = color.rgb32(20, 20, 20)

    # Animation timing constants
    WALK_CYCLE_SPEED: Final = 8.0  # radians per second
    BOB_SPEED: Final = 8.0
    TAIL_SWAY_SPEED: Final = 2.5
    BREATH_SPEED: Final = 1.8
    JUMP_DURATION: Final = 0.6  # seconds

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        # --- Build body parts as child entities ---

        # Torso (main body)
        self.torso = Entity(
            parent=self,
            model='cube',
            color=self.ORANGE,
            scale=(1.2, 1.0, 1.6),
            position=(0, 0.7, 0),
            origin=(0, 0, 0),
        )

        # Belly (cream patch on torso front)
        self.belly = Entity(
            parent=self.torso,
            model='cube',
            color=self.CREAM,
            scale=(0.9, 0.6, 0.08),
            position=(0, -0.2, 0.72),
            origin=(0, 0, 0),
        )

        # Neck (connects torso to head)
        self.neck = Entity(
            parent=self.torso,
            model='cube',
            color=self.ORANGE,
            scale=(0.6, 0.5, 0.6),
            position=(0, 0.65, 0.5),
            origin=(0, 0, 0),
        )

        # Head (large, cute)
        self.head = Entity(
            parent=self.neck,
            model='cube',
            color=self.ORANGE,
            scale=(1.2, 1.1, 1.1),
            position=(0, 0.7, 0.1),
            origin=(0, 0, 0),
        )

        # Muzzle (cream front of face)
        self.muzzle = Entity(
            parent=self.head,
            model='cube',
            color=self.CREAM,
            scale=(0.7, 0.5, 0.15),
            position=(0, -0.15, 0.68),
            origin=(0, 0, 0),
        )

        # Nose (dark, on muzzle)
        self.nose = Entity(
            parent=self.muzzle,
            model='sphere',
            color=self.NOSE_BLACK,
            scale=(0.18, 0.12, 0.12),
            position=(0, -0.05, 0.12),
            origin=(0, 0, 0),
        )

        # Eyes (dark, expressive)
        self.eye_left = Entity(
            parent=self.head,
            model='sphere',
            color=self.DARK,
            scale=(0.14, 0.16, 0.14),
            position=(-0.3, 0.15, 0.58),
            origin=(0, 0, 0),
        )
        self.eye_right = Entity(
            parent=self.head,
            model='sphere',
            color=self.DARK,
            scale=(0.14, 0.16, 0.14),
            position=(0.3, 0.15, 0.58),
            origin=(0, 0, 0),
        )

        # Ears (pointed cubes to mimic cones)
        self.ear_left = Entity(
            parent=self.head,
            model='cube',
            color=self.ORANGE,
            scale=(0.1, 0.55, 0.1),
            position=(-0.45, 0.55, -0.1),
            rotation=(20, 0, -15),
            origin=(0, 0, 0),
        )
        self.ear_right = Entity(
            parent=self.head,
            model='cube',
            color=self.ORANGE,
            scale=(0.1, 0.55, 0.1),
            position=(0.45, 0.55, -0.1),
            rotation=(20, 0, 15),
            origin=(0, 0, 0),
        )

        # Ear inner cream tips (cubes to mimic cones)
        self.ear_tip_left = Entity(
            parent=self.ear_left,
            model='cube',
            color=self.CREAM,
            scale=(0.2, 0.5, 0.2),
            position=(0, 0.1, 0),
            rotation=(0, 0, 0),
            origin=(0, 0, 0),
        )
        self.ear_tip_right = Entity(
            parent=self.ear_right,
            model='cube',
            color=self.CREAM,
            scale=(0.2, 0.5, 0.2),
            position=(0, 0.1, 0),
            rotation=(0, 0, 0),
            origin=(0, 0, 0),
        )

        # Four legs (distinct, with upper/lower segments for walk animation)
        self.legs: list[dict[str, Entity]] = []
        leg_positions = [
            (-0.45, -0.5, 0.5),   # front left
            (0.45, -0.5, 0.5),    # front right
            (-0.45, -0.5, -0.5),  # rear left
            (0.45, -0.5, -0.5),   # rear right
        ]
        for i, (lx, ly, lz) in enumerate(leg_positions):
            is_front = i < 2
            upper = Entity(
                parent=self.torso,
                model='cube',
                color=self.ORANGE,
                scale=(0.22, 0.55, 0.22),
                position=(lx, ly + 0.2, lz),
                origin=(0, 0.5, 0),
            )
            lower = Entity(
                parent=upper,
                model='cube',
                color=self.ORANGE,
                scale=(0.9, 1.1, 0.9),
                position=(0, -0.55, 0),
                origin=(0, 0.5, 0),
            )
            # Paw (slightly darker)
            paw = Entity(
                parent=lower,
                model='cube',
                color=self.DARK,
                scale=(1.1, 0.15, 1.1),
                position=(0, -0.6, 0),
                origin=(0, 0.5, 0),
            )
            self.legs.append({
                'upper': upper,
                'lower': lower,
                'paw': paw,
                'is_front': is_front,
                'side': -1 if i % 2 == 0 else 1,  # left = -1, right = 1
            })

        # Tail (fluffy, multi-segment for expressive sway)
        self.tail_segments: list[Entity] = []
        tail_base = Entity(
            parent=self.torso,
            model='cube',
            color=self.ORANGE,
            scale=(0.35, 0.35, 0.6),
            position=(0, 0.15, -0.9),
            origin=(0, 0, 0.5),
            rotation=(20, 0, 0),
        )
        self.tail_segments.append(tail_base)

        # Additional tail segments for fluffiness
        for seg_idx in range(1, 4):
            seg = Entity(
                parent=self.tail_segments[-1],
                model='cube',
                color=self.ORANGE if seg_idx < 3 else self.CREAM,  # cream tip
                scale=(0.85, 0.85, 1.0),
                position=(0, 0.05, -0.55),
                origin=(0, 0, 0.5),
                rotation=(-5 * seg_idx, 0, 0),
            )
            self.tail_segments.append(seg)

        # Tail tip (cream, slightly larger for fluff)
        self.tail_tip = Entity(
            parent=self.tail_segments[-1],
            model='sphere',
            color=self.CREAM,
            scale=(0.5, 0.55, 0.5),
            position=(0, 0.1, -0.4),
            origin=(0, 0, 0),
        )

        # --- Animation state ---
        self._walk_active: bool = False
        self._walk_phase: float = 0.0
        self._heading: float = 0.0  # degrees
        self._idle_time: float = 0.0
        self._jump_active: bool = False
        self._jump_timer: float = 0.0
        self._jump_phase: float = 0.0  # 0..1 during jump

        # Store original local positions/rotations for animation reference
        self._base_torso_pos = Vec3(self.torso.position)
        self._base_torso_scale = Vec3(self.torso.scale)
        self._base_neck_pos = Vec3(self.neck.position)
        self._base_head_pos = Vec3(self.head.position)
        self._base_leg_positions = [
            {
                'upper_pos': Vec3(leg['upper'].position),
                'upper_rot': Vec3(leg['upper'].rotation),
                'lower_rot': Vec3(leg['lower'].rotation),
            }
            for leg in self.legs
        ]
        self._base_tail_rots = [Vec3(seg.rotation) for seg in self.tail_segments]
        self._base_ear_rots = [
            Vec3(self.ear_left.rotation),
            Vec3(self.ear_right.rotation),
        ]
        self._base_tail_tip_scale = Vec3(self.tail_tip.scale)

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    def set_walking(self, active: bool, heading: float) -> None:
        """
        Start or stop walking animation.

        Args:
            active: True to walk, False to idle.
            heading: Heading in degrees (0 = +Z, 90 = +X). Applied to rotation_y.
        """
        self._walk_active = active
        self._heading = heading
        # Rotate the root entity to face heading
        self.rotation_y = heading
        if not active:
            self._walk_phase = 0.0

    def jump(self) -> None:
        """Trigger a jump animation. Does not move the root entity."""
        if not self._jump_active:
            self._jump_active = True
            self._jump_timer = 0.0
            self._jump_phase = 0.0

    def update_animation(self, dt: float) -> None:
        """
        Advance all animations by dt seconds.

        Call once per frame from the main loop. Updates breathing, tail sway,
        walk cycle, and jump animation using only child entity transforms.
        """
        if dt <= 0:
            return

        self._idle_time += dt

        # --- Jump animation (highest priority, overrides walk/idle for body) ---
        if self._jump_active:
            self._jump_timer += dt
            self._jump_phase = self._jump_timer / self.JUMP_DURATION
            if self._jump_phase >= 1.0:
                self._jump_active = False
                self._jump_phase = 0.0
                self._jump_timer = 0.0
                # Transition immediately to idle or walk; skip jump transform this frame
                if self._walk_active:
                    self._apply_walk_transform()
                else:
                    self._apply_idle_transform()
                return

            # Jump curve: quick up, slower down (parabolic ease)
            # phase 0..0.4 = rising, 0.4..1.0 = falling
            if self._jump_phase < 0.4:
                jump_height = math.sin(self._jump_phase / 0.4 * math.pi / 2) * 0.6
                squash = 1.0 - self._jump_phase / 0.4 * 0.15
            else:
                fall_phase = (self._jump_phase - 0.4) / 0.6
                jump_height = math.cos(fall_phase * math.pi / 2) * 0.6
                squash = 0.85 + fall_phase * 0.15

            self._apply_jump_transform(jump_height, squash)

        # --- Walking animation ---
        elif self._walk_active:
            self._walk_phase += dt * self.WALK_CYCLE_SPEED
            self._apply_walk_transform()

        # --- Idle animation (breathing + tail sway) ---
        else:
            self._apply_idle_transform()

    # ---------------------------------------------------------------------
    # Internal animation application
    # ---------------------------------------------------------------------

    def _apply_idle_transform(self) -> None:
        """Apply subtle breathing and tail sway at rest."""
        # Reset torso scale and rotation after jump
        self.torso.scale = self._base_torso_scale
        self.torso.rotation_x = 0.0

        # Reset neck/head rotation after jump
        self.neck.rotation_x = 0.0
        self.head.rotation_x = 0.0

        # Breathing: torso scales slightly, head bobs gently
        breath = math.sin(self._idle_time * self.BREATH_SPEED) * 0.02
        self.torso.scale_y = 1.0 + breath * 0.5
        self.torso.position = self._base_torso_pos + Vec3(0, breath * 0.15, 0)
        self.neck.position = self._base_neck_pos + Vec3(0, breath * 0.08, 0)
        self.head.position = self._base_head_pos + Vec3(0, breath * 0.05, 0)

        # Ears twitch slightly with breathing
        ear_twitch = math.sin(self._idle_time * self.BREATH_SPEED * 1.5) * 2.0
        self.ear_left.rotation_x = self._base_ear_rots[0].x + ear_twitch
        self.ear_right.rotation_x = self._base_ear_rots[1].x + ear_twitch
        self.ear_left.rotation_z = self._base_ear_rots[0].z
        self.ear_right.rotation_z = self._base_ear_rots[1].z

        # Tail sway (slow, relaxed)
        tail_sway = math.sin(self._idle_time * self.TAIL_SWAY_SPEED) * 12.0
        tail_wag = math.sin(self._idle_time * self.TAIL_SWAY_SPEED * 0.7) * 8.0
        for i, seg in enumerate(self.tail_segments):
            base = self._base_tail_rots[i]
            seg.rotation_z = base.z + tail_sway * (0.5 + i * 0.3)
            seg.rotation_x = base.x + tail_wag * (0.3 + i * 0.2)

        # Reset tail tip scale after jump
        self.tail_tip.scale = self._base_tail_tip_scale

        # Legs return to rest
        for i, leg in enumerate(self.legs):
            base = self._base_leg_positions[i]
            leg['upper'].position = base['upper_pos']
            leg['upper'].rotation = base['upper_rot']
            leg['lower'].rotation = base['lower_rot']
            leg['paw'].rotation_x = 0.0

    def _apply_walk_transform(self) -> None:
        """Apply walk cycle: leg movement, torso bob, head bob, tail bounce."""
        # Start from base scale after jump
        self.torso.scale = self._base_torso_scale
        self.tail_tip.scale = self._base_tail_tip_scale

        phase = self._walk_phase

        # Torso bob (up-down and slight pitch)
        bob_y = math.sin(phase * 2) * 0.05
        bob_pitch = math.sin(phase * 2) * 3.0
        self.torso.position = self._base_torso_pos + Vec3(0, bob_y, 0)
        self.torso.rotation_x = bob_pitch

        # Neck/head counter-motion for stability
        self.neck.position = self._base_neck_pos + Vec3(0, -bob_y * 0.3, 0)
        self.neck.rotation_x = -bob_pitch * 0.5
        self.head.position = self._base_head_pos + Vec3(0, -bob_y * 0.2, 0)
        self.head.rotation_x = -bob_pitch * 0.3

        # Ears bounce slightly
        ear_bounce = math.sin(phase * 2) * 4.0
        self.ear_left.rotation_x = self._base_ear_rots[0].x + ear_bounce
        self.ear_right.rotation_x = self._base_ear_rots[1].x + ear_bounce

        # Leg animation: front and rear pairs out of phase
        for i, leg in enumerate(self.legs):
            base = self._base_leg_positions[i]
            is_front = leg['is_front']
            side = leg['side']

            # Phase offset: front legs lead, rear legs follow; left/right opposite
            leg_phase = phase
            if not is_front:
                leg_phase += math.pi  # rear legs half-cycle offset
            if side < 0:
                leg_phase += math.pi  # left/right opposite

            # Upper leg: swings forward/back
            swing = math.sin(leg_phase) * 35.0  # degrees
            lift = max(0.0, math.sin(leg_phase)) * 25.0  # only lift on forward swing

            leg['upper'].rotation_x = base['upper_rot'].x + swing
            leg['upper'].rotation_z = base['upper_rot'].z + side * math.sin(leg_phase) * 8.0

            # Lower leg: extends when swinging forward, tucks when lifting
            leg['lower'].rotation_x = base['lower_rot'].x - lift * 0.7

            # Paw orientation follows lower leg
            leg['paw'].rotation_x = -leg['lower'].rotation_x * 0.3

        # Tail bounces with walk (upbeat)
        tail_bounce = math.sin(phase * 2) * 15.0
        tail_side = math.sin(phase) * 10.0
        for i, seg in enumerate(self.tail_segments):
            base = self._base_tail_rots[i]
            seg.rotation_x = base.x + tail_bounce * (0.4 + i * 0.2)
            seg.rotation_z = base.z + tail_side * (0.3 + i * 0.25)

    def _apply_jump_transform(self, jump_height: float, squash: float) -> None:
        """
        Apply jump transform: body lifts, squashes, legs tuck, tail flares.

        Args:
            jump_height: Vertical lift amount (0..~0.6).
            squash: Vertical scale factor for torso (1.0 = normal, <1 = squash).
        """
        # Torso: lift and squash
        self.torso.position = self._base_torso_pos + Vec3(0, jump_height, 0)
        self.torso.scale_y = squash
        self.torso.scale_x = 1.0 + (1.0 - squash) * 0.3  # widen slightly when squashed
        self.torso.scale_z = 1.0 + (1.0 - squash) * 0.2

        # Neck/head: stretch upward during rise, tuck during fall
        if self._jump_phase < 0.4:
            neck_stretch = self._jump_phase / 0.4 * 0.15
            head_tilt = -self._jump_phase / 0.4 * 10.0
        else:
            fall_phase = (self._jump_phase - 0.4) / 0.6
            neck_stretch = (1.0 - fall_phase) * 0.15
            head_tilt = -10.0 + fall_phase * 20.0  # look down on landing

        self.neck.position = self._base_neck_pos + Vec3(0, neck_stretch + jump_height * 0.3, 0)
        self.neck.rotation_x = head_tilt * 0.5
        self.head.position = self._base_head_pos + Vec3(0, neck_stretch * 0.5 + jump_height * 0.2, 0)
        self.head.rotation_x = head_tilt

        # Ears: flatten back during jump
        ear_flatten = -30.0 * (1.0 - abs(0.5 - self._jump_phase) * 2.0)
        self.ear_left.rotation_x = self._base_ear_rots[0].x + ear_flatten
        self.ear_right.rotation_x = self._base_ear_rots[1].x + ear_flatten
        self.ear_left.rotation_z = self._base_ear_rots[0].z - 20.0
        self.ear_right.rotation_z = self._base_ear_rots[1].z + 20.0

        # Legs: tuck all four legs up
        for i, leg in enumerate(self.legs):
            base = self._base_leg_positions[i]
            tuck = 60.0  # degrees
            leg['upper'].rotation_x = base['upper_rot'].x - tuck
            leg['upper'].rotation_z = base['upper_rot'].z
            leg['lower'].rotation_x = base['lower_rot'].x + tuck * 0.8
            leg['paw'].rotation_x = -leg['lower'].rotation_x * 0.5

        # Tail: flare up dramatically
        for i, seg in enumerate(self.tail_segments):
            base = self._base_tail_rots[i]
            flare = 40.0 + i * 15.0
            seg.rotation_x = base.x - flare
            seg.rotation_z = base.z + math.sin(self._jump_phase * math.pi * 2) * 10.0

        # Tail tip extra fluff
        self.tail_tip.scale = Vec3(0.6, 0.7, 0.6)