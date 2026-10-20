"""
Fox avatar implementation for Lumi Maze.
Uses Panda3D Actor for the 3D model and integrates with Ursina's Entity system.
All animation timing is handled manually in `update_animation` using the provided `dt`.
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

# Gameplay timing constants
EATING_DURATION = 0.65
JUMP_DURATION = 5.0
JUMP_HEIGHT = 3.2
# Time constant for shortest-angle yaw smoothing (~95% in 0.12 s).
YAW_SMOOTH_TAU = 0.04


def prepare_avatar_rendering():
    global _simplepbr_initialized
    if not _simplepbr_initialized:
        env_map_path = str(Path(__file__).parent / "assets" / "lighting" / "daylight.env")
        env_map = None
        if Path(env_map_path).exists():
            env_map = env_map_path

        simplepbr.init(
            exposure=0.0,
            enable_shadows=True,
            use_normal_maps=True,
            msaa_samples=4,
            shadow_bias=0.0005,
            env_map=env_map,
        )
        _simplepbr_initialized = True


class Fox(Entity):
    """Entity representing the controllable fox avatar.

    Public API:
        - `heading` (property): current desired heading in degrees.
        - `set_walking(active: bool, heading: float)`: enable/disable walking and set heading.
        - `jump()`: trigger a jump animation.
        - `celebrate_pickup()`: play the pickup celebration animation.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        prepare_avatar_rendering()

        # Load the fox model from package-relative path
        asset_path = Filename.fromOsSpecific(
            str(Path(__file__).parent / "assets" / "pxltiger_fox.glb")
        )
        self.actor = Actor(asset_path)
        self.actor.reparentTo(self)
        # Node shader with scene priority 10
        self.actor.setShader(application.base.render.getShader(), 10)
        # Already correct scale (1.10m normalized)
        self.actor.setScale(1)
        # Provisional orientation; coordinator checks final orientation
        self.actor.setH(180)
        self.actor.setP(0)
        self.actor.setR(0)

        # Pre-cache frame counts for deterministic manual posing
        self._clip_frames = {}
        for clip_name in ("Idle", "Run", "Jump", "InAir", "Fall", "Pickup"):
            n = self.actor.getNumFrames(clip_name)
            self._clip_frames[clip_name] = max(1, n)

        # Configure base loop play rates
        # Run: one stride = 0.36 sec. Clip is 15 frames @ 30fps = 0.5 sec.
        # Play rate = clip_duration / stride_duration = 0.5 / 0.36
        run_frames = self._clip_frames["Run"]
        run_duration = run_frames / 30.0
        self.actor.setPlayRate(run_duration / 0.36, "Run")
        # Idle: normal speed (60 frames @ 30fps = 2 sec loop)
        self.actor.setPlayRate(1.0, "Idle")
        # Pickup: 38 frames @ 30fps = 1.267 sec, but we want 0.65 sec total
        pickup_frames = self._clip_frames["Pickup"]
        pickup_duration = pickup_frames / 30.0
        self.actor.setPlayRate(pickup_duration / EATING_DURATION, "Pickup")

        # Internal state
        self._heading = 0.0          # Desired world heading (degrees)
        self._walking = False        # Is the walking state active?
        self._jumping = False        # Jump animation in progress (True from jump through landing)
        self._eating = False         # Pickup/eating animation in progress
        self._jump_timer = 0.0       # Accumulated time for current jump (exposed for QA)
        self._eat_timer = 0.0        # Accumulated time for current eating (exposed for QA)
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

        Updates `_heading` and lets `update_animation` turn the fox towards it smoothly.
        If `active` changes the base animation loop is switched accordingly;
        NEVER changes active clip while _jumping or _eating.
        """
        self._heading = heading
        self._walking = active

        desired = "Run" if active else "Idle"
        if desired != self._desired_loop:
            self._desired_loop = desired
            # Only switch animation if we are not in a special state.
            if not (self._jumping or self._eating):
                self.actor.loop(self._desired_loop)

    def jump(self):
        """Trigger a jump animation.

        Jump lasts 2.0 seconds with height curve 4*JUMP_HEIGHT*p*(1-p).
        _jumping must be True from jump through landing.
        Jump interrupts Eating safely and clears eating flag.
        """
        if self._jumping:
            return
        # Interrupt eating if active
        if self._eating:
            self._eating = False
            self._eat_timer = 0.0
        self._jumping = True
        self._jump_timer = 0.0
        # We'll manually pose frames in update_animation; stop any looping clip
        self.actor.stop()

    def celebrate_pickup(self):
        """Play the pickup celebration animation for 0.65 seconds.

        Does not interfere with stored walking state; resumes appropriate base loop when done.
        Main blocks movement for 0.65s.
        """
        if self._eating or self._jumping:
            return
        self._eating = True
        self._eat_timer = 0.0
        # We'll manually pose Pickup frames in update_animation
        self.actor.stop()

    # ---------------------------------------------------------------------
    # Animation clock – called explicitly by Game.update(dt).
    # ---------------------------------------------------------------------
    def update_animation(self, dt: float):
        """Advance animation timers and apply per-frame transformations.

        Parameters
        ----------
        dt: float
            Time elapsed since the previous frame (seconds).
        """
        if dt > 0.0:
            # Shortest-angle yaw smoothing with tau=0.04
            delta = ((self._heading - self.rotation_y + 180.0) % 360.0) - 180.0
            blend = 1.0 - math.exp(-dt / YAW_SMOOTH_TAU)
            if abs(delta) < 0.05 or abs(delta * (1.0 - blend)) < 0.05:
                self.rotation_y = self._heading
            else:
                self.rotation_y += delta * blend

        # Jump handling - manual posing, deterministic retiming
        if self._jumping:
            self._jump_timer += dt
            p = self._jump_timer / JUMP_DURATION
            if p > 1.0:
                p = 1.0

            # EXACT curve: 4*JUMP_HEIGHT*p*(1-p)
            y_offset = 4.0 * JUMP_HEIGHT * p * (1.0 - p)
            # World entity horizontal grid root stays on ground; translate actor-localY for flight only
            self.actor.setY(y_offset)

            # Manual frame posing based on progress
            jump_frames = self._clip_frames["Jump"]
            inair_frames = self._clip_frames["InAir"]
            fall_frames = self._clip_frames["Fall"]

            if p < 0.25:
                # First quarter: first half of Jump clip (0 to 50% of Jump frames)
                frame = min(jump_frames - 1, int((p / 0.25) * 0.5 * (jump_frames - 1)))
                self.actor.pose("Jump", frame)
            elif p < 0.75:
                # Middle half: loop InAir continuously with frame based on elapsed
                # InAir is 30 frames @ 30fps = 1 sec. Map p in [0.25, 0.75] to time in [0, 0.5]
                local_t = (p - 0.25) / 0.5  # 0..1 over middle half
                # Loop InAir: each second = 30 frames. Elapsed in this phase = local_t * 0.5 * JUMP_DURATION = local_t * 1.0
                # But simpler: just cycle through InAir frames based on total jump time
                frame = min(inair_frames - 1, int((self._jump_timer * 30.0) % inair_frames))
                self.actor.pose("InAir", frame)
            else:
                # Final quarter: second half of Jump clip for landing (50% to 100% of Jump frames)
                # Could use Fall clip if appropriate, but Jump second half is specified
                local_p = (p - 0.75) / 0.25  # 0..1 over final quarter
                frame = min(jump_frames - 1, int(0.5 * (jump_frames - 1) + local_p * 0.5 * (jump_frames - 1)))
                self.actor.pose("Jump", frame)

            if p >= 1.0:
                # Jump finished - reset position and state
                self.actor.setY(0)
                self._jumping = False
                self._jump_timer = 0.0
                # Return to stored base loop
                self.actor.loop(self._desired_loop)

        # Eating/Pickup handling - manual posing across full frames
        elif self._eating:
            self._eat_timer += dt
            if self._eat_timer >= EATING_DURATION:
                self._eating = False
                self._eat_timer = 0.0
                # Return to stored base loop
                self.actor.loop(self._desired_loop)
            else:
                # Manual pose Pickup across its full frames
                pickup_frames = self._clip_frames["Pickup"]
                progress = self._eat_timer / EATING_DURATION
                frame = min(pickup_frames - 1, int(progress * (pickup_frames - 1)))
                self.actor.pose("Pickup", frame)

        else:
            # Normal state: ensure base loop is playing
            # (actor.loop is idempotent if already playing that clip)
            if self.actor.getCurrentAnim() != self._desired_loop:
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
