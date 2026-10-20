"""
Fox avatar implementation for Lumi Maze.
Uses Panda3D Actor for the 3D model and integrates with Ursina's Entity system.
All animation timing is handled manually in `update` using the provided `dt`.
"""

from pathlib import Path
import math

from ursina import Entity, application
from panda3d.core import Filename, loadPrcFileData
from direct.actor.Actor import Actor
loadPrcFileData('', 'gltf-legacy-materials true')
import gltf  # noqa: F401 – required for loading glTF assets
import simplepbr

# SimplePBR should be initialized only once after the Ursina app exists.
_simplepbr_initialized = False

# Keep the pickup celebration and the gameplay arrival lock in sync.
EATING_DURATION = 0.65
JUMP_DURATION = 0.65
JUMP_HEIGHT = 1.1
# Time constant for shortest-angle yaw smoothing (~95% in 0.12 s).
YAW_SMOOTH_TAU = 0.04


def prepare_avatar_rendering():
    global _simplepbr_initialized
    if not _simplepbr_initialized:
        simplepbr.init(
            exposure=0.0,
            enable_shadows=True,
            use_normal_maps=True,
            msaa_samples=4,
            shadow_bias=0.0005,
        )
        _simplepbr_initialized = True


class Fox(Entity):
    """Entity representing the controllable fox avatar.

    Public API:
        - `heading` (property): current desired heading in degrees.
        - `set_walking(active: bool, heading: float)`: enable/disable walking and set heading.
        - `jump()`: trigger a jump animation.
        - `celebrate_pickup()`: play the eating animation.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        prepare_avatar_rendering()

        # Load the fox model
        asset_path = Filename.fromOsSpecific(
            str(Path(__file__).parent / "assets" / "quaternius_fox.gltf")
        )
        self.actor = Actor(asset_path)
        self.actor.reparentTo(self)
        self.actor.setShader(application.base.render.getShader(), 10)
        self.actor.setScale(0.5)
        # Model faces -Z; we keep a local heading of 180° so that a world heading of 0 aligns with +Z.
        self.actor.setH(180)
        self.actor.setP(0)
        # Each cell takes roughly a third of a second; match one visible stride to it.
        self.actor.setPlayRate(2.2, "Gallop")
        self.actor.setPlayRate(3.0, "Eating")
        self.actor.setPlayRate(1.5, "Gallop_Jump")

        # Internal state
        self._heading = 0.0          # Desired world heading (degrees)
        self._walking = False        # Is the walking state active?
        self._jumping = False        # Jump animation in progress?
        self._eating = False         # Eating animation in progress?
        self._jump_timer = 0.0       # Accumulated time for the current jump
        self._eat_timer = 0.0        # Accumulated time for the current eating animation
        self._desired_loop = "Idle"  # Base loop when not in a special animation

        # Start with idle animation
        self.actor.loop("Idle")

    def on_destroy(self):
        """Ursina's destroy() hook: release the Panda Actor."""
        self._cleanup_actor()

    # ---------------------------------------------------------------------
    # Public properties
    # ---------------------------------------------------------------------
    @property
    def heading(self) -> float:
        """Current desired heading (degrees)."""
        return self._heading

    # ---------------------------------------------------------------------
    # Control methods
    # ---------------------------------------------------------------------
    def set_walking(self, active: bool, heading: float):
        """Set walking state and desired heading.

        The method stores ``heading`` and lets :meth:`update_animation` turn the
        fox towards it smoothly.  If ``active`` changes the base animation loop
        is switched accordingly; repeating the same state does not restart the
        Gallop clip at a cell boundary.
        """
        self._heading = heading
        self._walking = active

        desired = "Gallop" if active else "Idle"
        if desired != self._desired_loop:
            self._desired_loop = desired
            # Only switch animation if we are not in a special state.
            if not (self._jumping or self._eating):
                self.actor.loop(self._desired_loop)

    def jump(self):
        """Trigger a jump animation.

        The jump lasts ~0.65 seconds. During the jump the fox's vertical position
        is driven by ``1.1 * sin(pi * progress)`` where ``progress`` ranges from
        0 to 1.  After the jump finishes the animation returns to the previously
        desired base loop and the actor-local Y is exactly zero again.
        """
        if self._jumping or self._eating:
            # Do not interrupt an ongoing special animation.
            return
        self._jumping = True
        self._jump_timer = 0.0
        self.actor.play("Gallop_Jump")  # Use play to start the clip once.

    def celebrate_pickup(self):
        """Play the eating animation for ~0.65 seconds.

        The eating animation does not interfere with the stored walking state; the
        fox will resume the appropriate base loop when the animation finishes.
        """
        if self._eating or self._jumping:
            return
        self._eating = True
        self._eat_timer = 0.0
        self.actor.play("Eating")

    # ---------------------------------------------------------------------
    # Animation clock – called explicitly by Game.update(dt).
    # ---------------------------------------------------------------------
    def update_animation(self, dt: float):
        """Advance animation timers and apply per‑frame transformations.

        Parameters
        ----------
        dt: float
            Time elapsed since the previous frame (seconds).
        """
        if dt > 0.0:
            # Shortest-angle yaw smoothing over roughly 0.12 seconds.  Keep
            # `_heading` (the target) untouched.
            delta = ((self._heading - self.rotation_y + 180.0) % 360.0) - 180.0
            blend = 1.0 - math.exp(-dt / YAW_SMOOTH_TAU)
            if abs(delta) < 0.05 or abs(delta * (1.0 - blend)) < 0.05:
                self.rotation_y = self._heading
            else:
                self.rotation_y += delta * blend

        # Jump handling
        if self._jumping:
            self._jump_timer += dt
            progress = min(self._jump_timer / JUMP_DURATION, 1.0)
            # Vertical bounce using sine wave.
            y_offset = JUMP_HEIGHT * math.sin(math.pi * progress)
            self.actor.setY(y_offset)
            if progress >= 1.0:
                # Jump finished – reset position and state.
                self.actor.setY(0)
                self._jumping = False
                # Return to stored base loop.
                self.actor.loop(self._desired_loop)
        # Eating handling
        elif self._eating:
            self._eat_timer += dt
            if self._eat_timer >= EATING_DURATION:
                self._eating = False
                # Return to stored base loop.
                self.actor.loop(self._desired_loop)

    # ---------------------------------------------------------------------
    # Cleanup – called when the entity is removed from the scene.
    # ---------------------------------------------------------------------
    def _cleanup_actor(self):
        """Release the Panda Actor exactly once, even if destroy is retried."""
        actor = getattr(self, "actor", None)
        if actor is None:
            return
        self.actor = None
        try:
            actor.cleanup()
        except Exception:
            pass

    def __del__(self):
        self._cleanup_actor()
