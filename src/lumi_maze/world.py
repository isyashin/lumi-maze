"""WorldView: floors, walls, exit portal, items and theme dressing.

The maze is assembled from modest primitives with separate wall body, plinth
and cap materials.  The surrounding garden is built from the verified CC0
nature kit in :mod:`lumi_maze.scenery`.
"""

import random
import math
from typing import Dict, Tuple
from dataclasses import dataclass

from ursina import Entity, color, destroy, application

from .core import Maze, Cell
from .textures import texture_for, ground_texture
from .scenery import GROUND_Y as SCENERY_GROUND_Y, populate_scenery, place_small_prop, place_food_prop
from .wall_mesh import WallBatch

CELL_SIZE = 3.0
WALL_HEIGHT = 1.55
WALL_THICKNESS = 0.26
FLOOR_Y = -0.12
GROUND_Y = -0.32

THEME_PALETTE = {
    'stone': {
        'floor': (232, 219, 193),
        'ground': (214, 232, 190),
        'body': (248, 218, 168),
        'cap': (255, 238, 195),
        'plinth': (143, 111, 73),
        'portal': (232, 201, 142),
    },
    'forest': {
        'floor': (214, 219, 182),
        'ground': (198, 228, 176),
        'body': (146, 184, 118),
        'cap': (183, 207, 137),
        'plinth': (75, 111, 58),
        'portal': (224, 190, 132),
    },
    'cave': {
        'floor': (154, 163, 178),
        'ground': (142, 150, 164),
        'body': (132, 145, 170),
        'cap': (182, 170, 205),
        'plinth': (78, 84, 106),
        'portal': (174, 193, 222),
    },
    'streams': {
        'floor': (184, 198, 179),
        'ground': (176, 215, 188),
        'body': (120, 172, 166),
        'cap': (146, 202, 188),
        'plinth': (61, 105, 100),
        'portal': (203, 213, 166),
    },
}


def _shade(rgb: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    return tuple(max(0, min(255, int(c * factor))) for c in rgb)


@dataclass
class ItemNode:
    """Container for an item's visual components."""
    root: Entity
    item_type: str
    bob_offset: float = 0.0
    rotation_speed: float = 0.0
    bob_amplitude: float = 0.12


class WorldView:
    """Visual representation of one maze level.

    Ownership:
      - self.root: parent of every entity belonging to this level
      - self.item_nodes: Cell -> ItemNode (items and exit portal)
    """

    def __init__(self, maze: Maze):
        self.maze = maze
        self.root = Entity()
        # Everything that never animates lives here so it can be flattened.
        self.static_root = Entity(parent=self.root)
        self.item_nodes: Dict[Cell, ItemNode] = {}
        self._cleared = False
        self._scenery_nodes = []
        self._scenery_bounds = []  # cached (node, bmin, bmax) for perimeter models
        self._scenery_orig_states = []  # original RenderState for each perimeter node

        theme_id = self._theme_id(maze.theme)
        dim_hash = (maze.width * 1000 + maze.height) & 0xFFFFFFFF
        self._rng = random.Random((theme_id << 24) ^ dim_hash ^ 0x9E3779B9)
        self._palette = THEME_PALETTE.get(maze.theme, THEME_PALETTE['forest'])

        self._floor_tex = texture_for(maze.theme, 'floor',
                                      seed=((theme_id << 16) ^ 0xF100) & 0xFFFFFFFF)
        self._wall_tex = texture_for(maze.theme, 'wall',
                                     seed=((theme_id << 16) ^ 0xA110) & 0xFFFFFFFF)

        self.walls = WallBatch(self.root, self._wall_tex, floor_y=FLOOR_Y)
        self._build_ground()
        self._build_floor()
        self._build_walls()
        self.walls.build()
        self._build_exit()
        self._build_items()
        self._build_decorations()
        self._scenery_nodes = populate_scenery(
            self.root, maze, CELL_SIZE, (theme_id << 24) ^ dim_hash
        )
        self._cache_scenery_bounds()
        self._finalize_static()

    # ------------------------------------------------------------------ #
    # Construction helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _theme_id(theme: str) -> int:
        return {
            'stone': 1,
            'forest': 2,
            'cave': 3,
            'streams': 4,
        }.get(theme, 0)

    def _cell_center(self, cell: Cell) -> Tuple[float, float]:
        x, z = cell
        return (x * CELL_SIZE, z * CELL_SIZE)

    @staticmethod
    def _pbr(entity: Entity) -> Entity:
        """Use the scene PBR shader on primitive surfaces so light works."""
        entity.setShader(application.base.render.getShader(), 0)
        return entity

    def _build_ground(self) -> None:
        """A modest, textured grass carpet outside the maze."""
        floor_w = self.maze.width * CELL_SIZE
        floor_h = self.maze.height * CELL_SIZE
        size_w = floor_w + 24.0
        size_h = floor_h + 24.0
        center = ((self.maze.width - 1) * CELL_SIZE / 2,
                  (self.maze.height - 1) * CELL_SIZE / 2)
        ground = Entity(
            parent=self.root,
            model='plane',
            scale=(size_w, 1, size_h),
            position=(center[0], GROUND_Y, center[1]),
            texture=ground_texture(),
            texture_scale=(size_w / 3.5, size_h / 3.5),
            color=color.rgb32(*self._palette['ground']),
        )
        self._pbr(ground)

    def _build_floor(self) -> None:
        """One calm continuous path instead of a noisy tile per cell."""
        floor_w = self.maze.width * CELL_SIZE
        floor_h = self.maze.height * CELL_SIZE
        floor = Entity(
            parent=self.root,
            model='plane',
            scale=(floor_w, 1, floor_h),
            position=((self.maze.width - 1) * CELL_SIZE / 2,
                      FLOOR_Y,
                      (self.maze.height - 1) * CELL_SIZE / 2),
            texture=self._floor_tex,
            texture_scale=(floor_w / 6.5, floor_h / 6.5),
            color=color.rgb32(*self._palette['floor']),
        )
        self._pbr(floor)

    def _build_walls(self) -> None:
        """Create each wall once, with a readable plinth and separate cap."""
        w, h = self.maze.width, self.maze.height

        for x in range(w):
            for z in range(h):
                cx, cz = self._cell_center((x, z))

                if x + 1 < w and not self.maze.is_open((x, z), (x + 1, z)):
                    self._create_wall(
                        pos=(cx + CELL_SIZE / 2, 0, cz),
                        scale=(WALL_THICKNESS, WALL_HEIGHT, CELL_SIZE),
                    )

                if z + 1 < h and not self.maze.is_open((x, z), (x, z + 1)):
                    self._create_wall(
                        pos=(cx, 0, cz + CELL_SIZE / 2),
                        scale=(CELL_SIZE, WALL_HEIGHT, WALL_THICKNESS),
                    )

        for z in range(h):
            cx, cz = self._cell_center((0, z))
            self._create_wall(
                pos=(cx - CELL_SIZE / 2, 0, cz),
                scale=(WALL_THICKNESS, WALL_HEIGHT, CELL_SIZE),
            )
            cx, cz = self._cell_center((w - 1, z))
            self._create_wall(
                pos=(cx + CELL_SIZE / 2, 0, cz),
                scale=(WALL_THICKNESS, WALL_HEIGHT, CELL_SIZE),
            )

        for x in range(w):
            cx, cz = self._cell_center((x, 0))
            self._create_wall(
                pos=(cx, 0, cz - CELL_SIZE / 2),
                scale=(CELL_SIZE, WALL_HEIGHT, WALL_THICKNESS),
            )
            cx, cz = self._cell_center((x, h - 1))
            self._create_wall(
                pos=(cx, 0, cz + CELL_SIZE / 2),
                scale=(CELL_SIZE, WALL_HEIGHT, WALL_THICKNESS),
            )

    def _create_wall(self, pos: Tuple[float, float, float],
                     scale: Tuple[float, float, float]) -> None:
        """Bake one wall body, cap and plinth into the shared wall batches.

        Subtle per-segment shade variation breaks up long walls without
        looking tiled; the batch keeps collision and maze data untouched.
        """
        variation = self._rng.uniform(0.94, 1.06)
        self.walls.add_wall(
            pos,
            scale,
            _shade(self._palette['body'], variation),
            _shade(self._palette['cap'], variation),
            _shade(self._palette['plinth'], variation),
        )

    def _build_exit(self) -> None:
        """A friendly, static garden arch around the exit cell."""
        ex, ez = self.maze.exit
        cx, cz = self._cell_center(self.maze.exit)
        base = FLOOR_Y

        portal_root = Entity(parent=self.root, position=(cx, 0, cz))
        frame = color.rgb32(*self._palette['portal'])
        wood = color.rgb32(129, 96, 62)

        neighbors = self.maze.neighbors(self.maze.exit)
        if neighbors:
            nx, nz = neighbors[0]
            dx, dz = nx - ex, nz - ez
            px, pz = -dz * .78, dx * .78
            beam_angle = math.degrees(math.atan2(dx, dz))
        else:
            px, pz = .78, 0
            beam_angle = 0
        column_h = 2.15
        beam_len = math.hypot(px * 2, pz * 2) + .34

        for sign in (1, -1):
            ox, oz = px * sign, pz * sign
            stone_base = Entity(
                parent=portal_root,
                model='cube',
                scale=(.36, .18, .36),
                position=(ox, base + .09, oz),
                color=frame,
            )
            self._pbr(stone_base)

            post = Entity(
                parent=portal_root,
                model='cube',
                scale=(.18, column_h, .18),
                position=(ox, base + column_h / 2 + .15, oz),
                color=wood,
            )
            self._pbr(post)

            collar = Entity(
                parent=portal_root,
                model='cube',
                scale=(.27, .12, .27),
                position=(ox, base + column_h + .20, oz),
                color=frame,
            )
            self._pbr(collar)

        beam = Entity(
            parent=portal_root,
            model='cube',
            scale=(beam_len, .17, .22),
            position=(0, base + column_h + .34, 0),
            rotation_y=beam_angle,
            color=frame,
        )
        self._pbr(beam)

        crest = Entity(
            parent=portal_root,
            model='cube',
            scale=(.52, .22, .27),
            position=(0, base + column_h + .49, 0),
            rotation_y=beam_angle,
            color=wood,
        )
        self._pbr(crest)

        lantern = Entity(
            parent=portal_root,
            model='sphere',
            scale=.29,
            position=(0, base + column_h + .10, 0),
            color=color.rgb32(255, 228, 158),
        )
        self._pbr(lantern)

        self.item_nodes[self.maze.exit] = ItemNode(
            root=portal_root,
            item_type='exit',
            bob_offset=self._rng.random() * math.tau,
            rotation_speed=0.0,
            bob_amplitude=0.0,
        )

    def _build_items(self) -> None:
        """Create the fruit and trampoline pickups."""
        for cell, item_type in self.maze.items.items():
            cx, cz = self._cell_center(cell)
            item_root = Entity(parent=self.root, position=(cx, 0, cz))

            if item_type == 'apple':
                self._build_apple(item_root)
            elif item_type == 'strawberry':
                self._build_strawberry(item_root)
            elif item_type == 'trampoline':
                self._build_trampoline(item_root)

            self.item_nodes[cell] = ItemNode(
                root=item_root,
                item_type=item_type,
                bob_offset=self._rng.random() * math.tau,
                rotation_speed=0.0 if item_type == 'trampoline'
                else self._rng.uniform(20.0, 40.0),
                bob_amplitude=0.035 if item_type == 'trampoline' else 0.12,
            )

    def _build_apple(self, root: Entity) -> None:
        place_food_prop(root, 'apple')

    def _build_strawberry(self, root: Entity) -> None:
        place_food_prop(root, 'strawberry')

    def _build_trampoline(self, root: Entity) -> None:
        """A small wooden garden trampoline with a soft teal pad."""
        base = Entity(
            parent=root,
            model='cube',
            scale=(1.34, .15, 1.34),
            position=(0, .075, 0),
            color=color.rgb32(112, 83, 55),
        )
        self._pbr(base)

        rim = Entity(
            parent=root,
            model='sphere',
            scale=(1.20, .14, 1.20),
            position=(0, .17, 0),
            color=color.rgb32(77, 98, 72),
        )
        self._pbr(rim)

        pad = Entity(
            parent=root,
            model='sphere',
            scale=(1.02, .12, 1.02),
            position=(0, .285, 0),
            color=color.rgb32(91, 177, 156),
        )
        self._pbr(pad)

        # Four small posts make the bounce feel deliberate rather than neon.
        for dx, dz in ((-.54, -.54), (.54, -.54), (-.54, .54), (.54, .54)):
            post = Entity(
                parent=root,
                model='cube',
                scale=(.10, .32, .10),
                position=(dx, .17, dz),
                color=color.rgb32(133, 99, 63),
            )
            self._pbr(post)
            knob = Entity(
                parent=root,
                model='sphere',
                scale=.11,
                position=(dx, .36, dz),
                color=color.rgb32(232, 196, 108),
            )
            self._pbr(knob)

        for angle in (0, 90):
            seam = Entity(
                parent=root,
                model='cube',
                scale=(1.07, .012, .028),
                position=(0, .352, 0),
                rotation_y=angle,
                color=color.rgb32(196, 221, 179),
            )
            self._pbr(seam)

        center = Entity(
            parent=root,
            model='sphere',
            scale=.11,
            position=(0, .36, 0),
            color=color.rgb32(245, 219, 128),
        )
        self._pbr(center)

    def _build_decorations(self) -> None:
        """Low corner plantings and a few theme accents away from lane centres."""
        w, h = self.maze.width, self.maze.height
        cells = [(x, z) for x in range(w) for z in range(h)]
        self._rng.shuffle(cells)
        max_decor = min(68, max(22, (w * h) // 2))
        placed = 0

        for cell in cells:
            if placed >= max_decor:
                break
            if cell == self.maze.exit or cell in self.maze.items:
                continue
            if self._rng.random() < .38:
                continue

            cx, cz = self._cell_center(cell)
            corners = [(-1.10, -1.10), (1.10, -1.10),
                       (-1.10, 1.10), (1.10, 1.10)]
            self._rng.shuffle(corners)
            for ox, oz in corners:
                wx, wz = cx + ox, cz + oz
                if not (-CELL_SIZE / 2 + .2 < wx
                        < (w - .5) * CELL_SIZE - .2):
                    continue
                if not (-CELL_SIZE / 2 + .2 < wz
                        < (h - .5) * CELL_SIZE - .2):
                    continue
                place_small_prop(self.static_root, self.maze.theme, wx,
                                 FLOOR_Y + .02, wz, self._rng)
                placed += 1
                break

        if self.maze.theme == 'cave':
            self._build_crystal_accents()
        elif self.maze.theme == 'streams':
            self._build_water_accents()

    def _finalize_static(self) -> None:
        """Flatten only low interior decorative props; keep perimeter models separate."""
        self.static_root.clear_model_nodes()
        self.static_root.flattenStrong()
        # Perimeter scenery nodes remain individual NodePaths (in self.root), not flattened.
        # self._scenery_nodes retains references for visibility checks.

    def _cache_scenery_bounds(self) -> None:
        """Cache tight world/root bounds for each perimeter scenery model once."""
        from panda3d.core import TransparencyAttrib
        self._scenery_bounds.clear()
        self._scenery_orig_states.clear()

        for node in self._scenery_nodes:
            if node.isEmpty():
                continue
            node.setTag('lumi_shadow','masked')
            try:
                # Get tight bounds in root space
                bmin, bmax = node.getTightBounds(self.root)
                self._scenery_bounds.append((node, bmin, bmax))
                # Cache original render state for exact restoration
                self._scenery_orig_states.append((node, node.getState()))
                # Ensure transparency is set up for dual-pass alpha blending
                node.setTransparency(TransparencyAttrib.MDual, 20)
            except Exception:
                # Skip nodes that can't provide bounds
                continue

    def _wall_sides(self, cell: Cell):
        x, z = cell
        sides = []
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, nz = x + dx, z + dz
            if not (0 <= nx < self.maze.width and 0 <= nz < self.maze.height):
                sides.append((dx, dz))
            elif not self.maze.is_open(cell, (nx, nz)):
                sides.append((dx, dz))
        return sides

    def _accent_spots(self, limit: int):
        """Return shuffled wall-side positions that stay out of lane centres."""
        cells = [(x, z) for x in range(self.maze.width)
                 for z in range(self.maze.height)
                 if (x, z) != self.maze.exit and (x, z) not in self.maze.items]
        self._rng.shuffle(cells)
        spots = []
        for cell in cells:
            sides = self._wall_sides(cell)
            if not sides:
                continue
            dx, dz = self._rng.choice(sides)
            cx, cz = self._cell_center(cell)
            # Sit right beside the wall, not on the walking centre line.
            wx = cx + dx * 1.28 + (-dz) * self._rng.uniform(-.62, .62)
            wz = cz + dz * 1.28 + (dx) * self._rng.uniform(-.62, .62)
            spots.append((wx, wz, dx, dz))
            if len(spots) >= limit:
                break
        return spots

    def _build_crystal_accents(self) -> None:
        """Small cool crystal clusters at cave wall feet."""
        crystal_colors = ((96, 132, 184), (122, 158, 207), (150, 184, 225))
        for wx, wz, _dx, _dz in self._accent_spots(24):
            for _ in range(self._rng.randint(2, 4)):
                height = self._rng.uniform(.20, .52)
                width = self._rng.uniform(.07, .15)
                shard = Entity(
                    parent=self.root,
                    model='cube',
                    scale=(width, height, width),
                    position=(wx + self._rng.uniform(-.18, .18),
                              FLOOR_Y + height / 2,
                              wz + self._rng.uniform(-.18, .18)),
                    rotation=(self._rng.uniform(-12, 12),
                              self._rng.uniform(0, 360),
                              self._rng.uniform(-12, 12)),
                    color=color.rgb32(*self._rng.choice(crystal_colors)),
                )
                self._pbr(shard)

    def _build_water_accents(self) -> None:
        """Shallow blue-green pools along stream walls."""
        for wx, wz, _dx, _dz in self._accent_spots(26):
            pool = Entity(
                parent=self.root,
                model='sphere',
                scale=(self._rng.uniform(.38, .68), .018,
                       self._rng.uniform(.26, .46)),
                position=(wx, FLOOR_Y + .018, wz),
                color=color.rgb32(58, 143, 148),
            )
            self._pbr(pool)
            glint = Entity(
                parent=self.root,
                model='sphere',
                scale=(.22, .010, .14),
                position=(wx + .05, FLOOR_Y + .031, wz - .03),
                color=color.rgb32(126, 198, 184),
            )
            self._pbr(glint)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def remove_item(self, cell: Cell) -> None:
        """Destroy a collected item (the exit portal is kept)."""
        node = self.item_nodes.pop(cell, None)
        if node and node.item_type != 'exit':
            destroy(node.root)

    def update_visibility(self, camera_pos, fox_pos, dt: float) -> None:
        """Update wall and scenery transparency for camera/fox sightline occlusion."""
        # Walls: per-vertex alpha via WallBatch
        self.walls.update_visibility(camera_pos, fox_pos, dt)

        # Scenery: per-node color scale alpha with MMultisample
        if not self._scenery_bounds:
            return

        from panda3d.core import TransparencyAttrib
        cam = camera_pos
        fox = fox_pos
        try:
            cam_pos = (float(cam.x), float(cam.y), float(cam.z))
            fox_pos_vec = (float(fox.x), float(fox.y), float(fox.z))
        except AttributeError:
            cam_pos = (float(cam[0]), float(cam[1]), float(cam[2]))
            fox_pos_vec = (float(fox[0]), float(fox[1]), float(fox[2]))

        foot_target = (fox_pos_vec[0], fox_pos_vec[1] + 0.30, fox_pos_vec[2])
        chest_target = (fox_pos_vec[0], fox_pos_vec[1] + 0.95, fox_pos_vec[2])
        BOUNDS_EXPANSION = 0.30

        for idx, (node, bmin, bmax) in enumerate(self._scenery_bounds):
            if node.isEmpty():
                continue

            # Expanded bounds for readability
            bmin_exp = (bmin[0] - BOUNDS_EXPANSION, bmin[1] - BOUNDS_EXPANSION, bmin[2] - BOUNDS_EXPANSION)
            bmax_exp = (bmax[0] + BOUNDS_EXPANSION, bmax[1] + BOUNDS_EXPANSION, bmax[2] + BOUNDS_EXPANSION)

            # Check camera inside expanded bounds
            cam_inside = (bmin_exp[0] <= cam_pos[0] <= bmax_exp[0] and
                          bmin_exp[1] <= cam_pos[1] <= bmax_exp[1] and
                          bmin_exp[2] <= cam_pos[2] <= bmax_exp[2])

            # Check ray hits (foot and chest)
            from .wall_mesh import _ray_hits_aabb
            occluding = cam_inside or _ray_hits_aabb(cam_pos, foot_target, bmin_exp, bmax_exp) or \
                        _ray_hits_aabb(cam_pos, chest_target, bmin_exp, bmax_exp)

            if occluding:
                # Semi-transparent: set color scale alpha ~0.22, use MDual
                node.setColorScale(1, 1, 1, 0.22, 100)  # priority 100 overrides
                node.setTransparency(TransparencyAttrib.MDual, 20)
            else:
                # Restore exact original RenderState (including any glTF transparency/alpha mode)
                orig_state = self._scenery_orig_states[idx][1] if idx < len(self._scenery_orig_states) else None
                if orig_state:
                    node.setState(orig_state)
                else:
                    node.clearColorScale()
                    node.setTransparency(TransparencyAttrib.MDual, 20)

    def update(self, dt: float) -> None:
        """Bob and rotate pickups; the exit arch remains static."""
        for node in self.item_nodes.values():
            root = node.root
            if not root or not root.enabled:
                continue

            node.bob_offset += dt * 2.0
            root.y = math.sin(node.bob_offset) * node.bob_amplitude

            if node.rotation_speed:
                root.rotation_y += dt * node.rotation_speed

    def clear(self) -> None:
        """Destroy every entity owned by this level. Safe to call twice."""
        if self._cleared:
            return
        destroy(self.root)
        self.root = None
        self.item_nodes.clear()
        self._scenery_nodes.clear()
        self._scenery_bounds.clear()
        self._scenery_orig_states.clear()
        self._cleared = True
