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

def prepare_avatar_rendering():
    global _simplepbr_initialized
    if not _simplepbr_initialized:
        simplepbr.init(exposure=-1.0)
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
        # Each cell takes roughly a quarter second; match one visible stride to it.
        self.actor.setPlayRate(2.2, "Gallop")
        self.actor.setPlayRate(3.0, "Eating")
        self.actor.setPlayRate(1.5, "Gallop_Jump")

        # Internal state
        self._heading = 0.0          # Desired world heading (degrees)
        self._walking = False       # Is the walking state active?
        self._jumping = False       # Jump animation in progress?
        self._eating = False        # Eating animation in progress?
        self._jump_timer = 0.0      # Accumulated time for the current jump
        self._eat_timer = 0.0       # Accumulated time for the current eating animation
        self._desired_loop = "Idle"  # Base loop when not in a special animation

        # Start with idle animation
        self.actor.loop("Idle")

    # ---------------------------------------------------------------------
    # Public properties
    # ---------------------------------------------------------------------
    @property
    def heading(self) -> float:
        """Current heading (degrees)."""
        return self._heading

    # ---------------------------------------------------------------------
    # Control methods
    # ---------------------------------------------------------------------
    def set_walking(self, active: bool, heading: float):
        """Set walking state and desired heading.

        The method always stores ``heading`` and updates the entity's ``rotation_y``
        so that external code sees the correct orientation.  If ``active`` changes
        the base animation loop is switched accordingly; otherwise only the stored
        heading is updated.
        """
        # Store heading and reflect it on the root entity.
        self._heading = heading
        self.rotation_y = heading

        if active != self._walking:
            self._walking = active
            self._desired_loop = "Gallop" if active else "Idle"
            # Only switch animation if we are not in a special state.
            if not (self._jumping or self._eating):
                self.actor.loop(self._desired_loop)

    def jump(self):
        """Trigger a jump animation.

        The jump lasts ~0.65 seconds. During the jump the fox's vertical position is
        driven by ``0.45 * sin(pi * progress)`` where ``progress`` ranges from 0 to 1.
        After the jump finishes the animation returns to the previously desired
        base loop (walk or idle).
        """
        if self._jumping or self._eating:
            # Do not interrupt an ongoing special animation.
            return
        self._jumping = True
        self._jump_timer = 0.0
        self.actor.play("Gallop_Jump")  # Use play to start the clip once.

    def celebrate_pickup(self):
        """Play the eating animation for ~0.9 seconds.

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
        # Jump handling
        if self._jumping:
            self._jump_timer += dt
            progress = min(self._jump_timer / 0.65, 1.0)
            # Vertical bounce using sine wave.
            y_offset = 0.45 * math.sin(math.pi * progress)
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
            if self._eat_timer >= 0.9:
                self._eating = False
                # Return to stored base loop.
                self.actor.loop(self._desired_loop)

    # ---------------------------------------------------------------------
    # Cleanup – called when the entity is removed from the scene.
    # ---------------------------------------------------------------------
    def __del__(self):
        try:
            self.actor.cleanup()
        except Exception:
            pass
