"""Scenery helpers built from the verified CC0 nature kit.

Every prop is parented to the level root, grounded from its real bounding box
and rendered with the scene PBR shader so it receives light and shadows.
Models are only requested through Panda's loader (which caches their data), and
all placement is deterministic for a given maze seed.
"""

from pathlib import Path
import math
import random
from typing import List, Tuple

from panda3d.core import Filename
from ursina import application

ASSETS = Path(__file__).parent / "assets" / "nature"
FOOD_ASSETS = Path(__file__).parent / "assets" / "food"
MEGAKIT = Path(__file__).parent / "assets" / "megakit"

# The painted grass carpet sits just below the walkable stone path.
GROUND_Y = -0.30

TREE_FILES = ("CommonTree_1.gltf", "CommonTree_2.gltf", "Pine_1.gltf")
BUSH_FILES = ("Bush_Common.gltf", "Bush_Common_Flowers.gltf", "Fern_1.gltf")
FLOWER_FILES = ("Flower_3_Group.gltf", "Flower_4_Group.gltf", "Grass_Wispy_Short.gltf")
ROCK_FILES = ("Rock_Medium_1.gltf", "Rock_Medium_2.gltf")
MUSHROOM_FILE = "Mushroom_Common.gltf"

# Compact plantings used inside cells: always in a corner and always low.
SMALL_PROPS = {
    "stone": [
        ("Rock_Medium_1.gltf", .16, .25),
        ("Bush_Common.gltf", .18, .29),
        ("Flower_4_Group.gltf", .15, .24),
        ("Grass_Wispy_Short.gltf", .18, .28),
        ("Mushroom_Common.gltf", .26, .38),
    ],
    "forest": [
        ("Bush_Common_Flowers.gltf", .18, .30),
        ("Fern_1.gltf", .16, .27),
        ("Flower_3_Group.gltf", .15, .25),
        ("Grass_Wispy_Short.gltf", .20, .32),
        ("Mushroom_Common.gltf", .25, .40),
    ],
    "cave": [
        ("Rock_Medium_2.gltf", .13, .22),
        ("Fern_1.gltf", .13, .21),
        ("Mushroom_Common.gltf", .19, .29),
        ("Rock_Medium_1.gltf", .11, .18),
    ],
    "streams": [
        ("Bush_Common.gltf", .18, .28),
        ("Flower_3_Group.gltf", .15, .24),
        ("Grass_Wispy_Short.gltf", .22, .34),
        ("Rock_Medium_2.gltf", .13, .21),
    ],
}


def _place_model(root, file_name: str, x: float, ground_y: float, z: float,
                 scale: float, heading: float):
    """Load, ground and return one scenery model, or ``None`` when missing."""
    path = MEGAKIT / file_name
    try:
        model = application.base.loader.loadModel(Filename.fromOsSpecific(str(path)))
    except Exception:
        return None
    if not model:
        return None

    model.reparentTo(root)
    model.setShader(application.base.render.getShader(), 0)
    model.setScale(scale)
    model.setH(heading)
    model.setPos(x, 0, z)

    # glTF origins are not consistently at ground level.  Compensate using the
    # evaluated bounds so trunks, mushrooms and rocks never hover or sink.
    try:
        low, _high = model.getTightBounds(application.base.render)
        model.setY(ground_y - low.getY())
    except Exception:
        model.setY(ground_y)
    return model


def place_small_prop(root, theme, x, y, z, rng):
    """A compact, non-colliding detail near a cell corner."""
    options = SMALL_PROPS.get(theme, SMALL_PROPS["forest"])
    name, s0, s1 = rng.choice(options)
    return _place_model(
        root, name, x, y, z,
        rng.uniform(s0, s1),
        rng.uniform(0, 360),
    )


def place_food_prop(root, fruit):
    """Place a recognizable fruit pickup from the CC0 Kenney Food Kit."""
    model = application.base.loader.loadModel(
        Filename.fromOsSpecific(str(FOOD_ASSETS / f"{fruit}.glb"))
    )
    model.reparentTo(root)
    model.setShader(application.base.render.getShader(), 0)
    model.setScale(4.3 if fruit == "apple" else 5.0)
    model.setY(.28)
    return model


def _choose_kind(theme: str, depth: float, rnd: random.Random) -> str:
    """Pick a plant type appropriate for the theme and distance from the maze."""
    if theme == "cave":
        # Caves are framed with boulders, ferns and mushrooms only.
        if depth < 3.0:
            return rnd.choice(("rock", "fern", "mushroom"))
        return rnd.choice(("cliff", "cliff", "rock", "rock",
                           "fern", "fern", "mushroom", "mushroom"))

    if depth < 2.1:
        return rnd.choice(("bush", "flower", "grass", "rock", "mushroom"))

    weights = {
        "stone": ("tree", "tree", "tree", "bush", "bush", "flower", "rock"),
        "forest": ("tree", "tree", "tree", "tree", "bush", "bush",
                   "flower", "mushroom", "rock"),
        "streams": ("tree", "tree", "tree", "bush", "bush", "flower",
                    "flower", "grass", "rock"),
    }.get(theme, ("tree", "tree", "bush", "flower"))
    return rnd.choice(weights)


def _spawn_kind(root, kind: str, x: float, z: float, rnd: random.Random):
    """Spawn a perimeter prop with a believable, bounded size."""
    heading = rnd.uniform(0, 360)
    if kind == "tree":
        scale = rnd.uniform(.50, .70)
        return _place_model(root, rnd.choice(TREE_FILES), x, GROUND_Y, z,
                            scale, heading)
    if kind == "pine":
        scale = rnd.uniform(.55, .72)
        return _place_model(root, "Pine_1.gltf", x, GROUND_Y, z, scale, heading)
    if kind == "bush":
        scale = rnd.uniform(.42, .72)
        return _place_model(root, rnd.choice(BUSH_FILES), x, GROUND_Y, z,
                            scale, heading)
    if kind == "flower":
        scale = rnd.uniform(.20, .32)
        return _place_model(root, rnd.choice(FLOWER_FILES), x, GROUND_Y, z,
                            scale, heading)
    if kind == "grass":
        scale = rnd.uniform(.28, .46)
        return _place_model(root, "Grass_Wispy_Short.gltf", x, GROUND_Y, z,
                            scale, heading)
    if kind == "fern":
        scale = rnd.uniform(.24, .42)
        return _place_model(root, "Fern_1.gltf", x, GROUND_Y, z, scale, heading)
    if kind == "mushroom":
        scale = rnd.uniform(.28, .48)
        return _place_model(root, MUSHROOM_FILE, x, GROUND_Y, z, scale, heading)
    if kind == "cliff":
        # Large boulders (~3-5 m tall) frame the cave perimeter.
        scale = rnd.uniform(1.5, 2.2)
        return _place_model(root, rnd.choice(ROCK_FILES), x, GROUND_Y, z,
                            scale, heading)
    scale = rnd.uniform(.40, .72)
    return _place_model(root, rnd.choice(ROCK_FILES), x, GROUND_Y, z,
                        scale, heading)


def _kind_gap(kind: str) -> float:
    return {
        "tree": 1.35, "pine": 1.25, "rock": .75, "bush": .55,
        "cliff": 2.3,
        "flower": .28, "grass": .30, "fern": .34, "mushroom": .24,
    }.get(kind, .4)


def populate_scenery(root, maze, cell_size, seed):
    """Build a dense, bounded garden belt around the complete maze.

    Returns the list of created models.  Nothing is placed inside the maze
    footprint, so corridors and the camera foreground remain readable.
    """
    rnd = random.Random(seed)
    w, h = maze.width, maze.height
    theme = getattr(maze, "theme", "forest")
    if theme not in ("stone", "forest", "cave", "streams"):
        theme = "forest"

    start = getattr(maze, "start", (0, 0))
    sx = start[0] * cell_size if isinstance(start, (tuple, list)) else 0.0
    sz = start[1] * cell_size if isinstance(start, (tuple, list)) else 0.0
    cam_x, cam_z = sx - 5.0, sz - 5.0

    inner_x0 = -cell_size / 2
    inner_x1 = (w - .5) * cell_size
    inner_z0 = -cell_size / 2
    inner_z1 = (h - .5) * cell_size

    loaded: List = []
    placed: List[Tuple[float, float, float]] = []

    def outside_maze(x: float, z: float, pad: float = 0.9) -> bool:
        return not (inner_x0 - pad < x < inner_x1 + pad
                    and inner_z0 - pad < z < inner_z1 + pad)

    def can_add(kind: str, x: float, z: float) -> bool:
        if not outside_maze(x, z, 1.0):
            return False
        # Leave a clear window between the camera and the start cell.
        if kind in ("tree", "pine", "bush", "cliff"):
            if math.hypot(x - cam_x, z - cam_z) < 3.0:
                return False
            if (x < sx - .4 and z < sz - .4
                    and math.hypot(x - sx, z - sz) < 7.8):
                return False
        gap = _kind_gap(kind)
        for px, pz, pgap in placed:
            if (x - px) ** 2 + (z - pz) ** 2 < (gap + pgap) ** 2 * .36:
                return False
        return True

    def add(kind: str, x: float, z: float) -> bool:
        if not can_add(kind, x, z):
            return False
        model = _spawn_kind(root, kind, x, z, rnd)
        if model is None:
            return False
        loaded.append(model)
        placed.append((x, z, _kind_gap(kind)))
        return True

    # A few deliberate anchors frame the start: trees to the west and south,
    # plus low flowers/bushes just outside the boundary wall.  The south-west
    # camera corridor itself stays open.
    anchors = (
        (-4.6, 1.8, "tree"),
        (1.8, -4.6, "tree"),
        (-6.8, 4.9, "tree"),
        (4.9, -6.8, "tree"),
        (-2.8, -2.8, "bush"),
        (-2.5, .9, "flower"),
        (.9, -2.5, "flower"),
    )
    if theme == "cave":
        # Boulder, fern and mushroom framing instead of a tree/pine belt.
        anchors = (
            (-4.6, 1.8, "cliff"),
            (1.8, -4.6, "cliff"),
            (-6.8, 4.9, "rock"),
            (4.9, -6.8, "rock"),
            (-2.8, -2.8, "fern"),
            (-2.5, .9, "mushroom"),
            (.9, -2.5, "mushroom"),
        )
    for dx, dz, kind in anchors:
        add(kind, sx + dx, sz + dz)

    target = min(220, 90 + w * 6)
    attempts = target * 18
    for _ in range(attempts):
        if len(loaded) >= target:
            break
        side = rnd.randrange(4)
        depth = rnd.uniform(1.0, 11.5)
        if side == 0:      # west
            x = inner_x0 - depth
            z = rnd.uniform(inner_z0 - 9.0, inner_z1 + 9.0)
        elif side == 1:    # east
            x = inner_x1 + depth
            z = rnd.uniform(inner_z0 - 9.0, inner_z1 + 9.0)
        elif side == 2:    # south
            x = rnd.uniform(inner_x0 - 9.0, inner_x1 + 9.0)
            z = inner_z0 - depth
        else:              # north
            x = rnd.uniform(inner_x0 - 9.0, inner_x1 + 9.0)
            z = inner_z1 + depth

        kind = _choose_kind(theme, depth, rnd)
        if kind in ("tree", "pine") and depth < 2.4:
            kind = "bush" if theme != "cave" else "rock"
        add(kind, x, z)

    return loaded
