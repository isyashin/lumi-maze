from pathlib import Path
import random
from panda3d.core import Filename
from ursina import application

ASSETS = Path(__file__).parent / "assets" / "nature"
FOOD_ASSETS = Path(__file__).parent / "assets" / "food"

TREES = ["tree_oak.glb", "tree_default.glb", "tree_pineRoundA.glb"]
BUSHES = ["plant_bushDetailed.glb"]
ROCKS = ["rock_largeA.glb", "cliff_block_stone.glb", "cliff_block_rock.glb"]
STREAM = ["flower_yellowA.glb", "mushroom_red.glb"]

SMALL_PROPS = {
    "stone": [("rock_largeA.glb", 1.0), ("plant_bushDetailed.glb", 1.4), ("mushroom_red.glb", 3.0)],
    "forest": [("plant_bushDetailed.glb", 1.6), ("flower_yellowA.glb", 3.2), ("mushroom_red.glb", 3.0)],
    "cave": [("rock_largeA.glb", 1.0), ("cliff_block_rock.glb", .75), ("cliff_block_stone.glb", .75)],
    "streams": [("plant_bushDetailed.glb", 1.4), ("flower_yellowA.glb", 3.2), ("rock_largeA.glb", .9)],
}


def place_small_prop(root, theme, x, y, z, rng):
    """A compact, non-colliding detail near a cell corner."""
    name, scale = rng.choice(SMALL_PROPS[theme])
    model = application.base.loader.loadModel(Filename.fromOsSpecific(str(ASSETS / name)))
    model.reparentTo(root)
    model.setShader(application.base.render.getShader(), 10)
    model.setPos(x, y, z)
    model.setH(rng.uniform(0, 360))
    model.setScale(scale * rng.uniform(.85, 1.12))
    return model


def place_food_prop(root, fruit):
    """Place a recognizable fruit pickup from the CC0 Kenney Food Kit."""
    model = application.base.loader.loadModel(
        Filename.fromOsSpecific(str(FOOD_ASSETS / f"{fruit}.glb"))
    )
    model.reparentTo(root)
    model.setShader(application.base.render.getShader(), 10)
    model.setScale(4.3 if fruit == "apple" else 5.0)
    model.setY(.28)
    return model


def populate_scenery(root, maze, cell_size, seed):
    rnd = random.Random(seed)
    w, h = maze.width, maze.height
    theme = getattr(maze, "theme", "forest")
    start = getattr(maze, "start", (0, 0))
    exit_ = getattr(maze, "exit", (w - 1, h - 1))
    # world positions of start/exit (cell centers)
    sx = start[0] * cell_size if isinstance(start, (tuple, list)) else 0
    sz = start[1] * cell_size if isinstance(start, (tuple, list)) else 0
    ex = exit_[0] * cell_size if isinstance(exit_, (tuple, list)) else (w - 1) * cell_size
    ez = exit_[1] * cell_size if isinstance(exit_, (tuple, list)) else (h - 1) * cell_size

    inner_x0 = -cell_size / 2
    inner_x1 = (w - 0.5) * cell_size
    inner_z0 = -cell_size / 2
    inner_z1 = (h - 0.5) * cell_size
    out_x0 = inner_x0 - 8
    out_x1 = inner_x1 + 8
    out_z0 = inner_z0 - 8
    out_z1 = inner_z1 + 8

    def near_start_exit(x, z):
        if (x - sx) ** 2 + (z - sz) ** 2 < 49:
            return True
        if (x - ex) ** 2 + (z - ez) ** 2 < 49:
            return True
        return False

    # asset pools with scale ranges
    if theme == "cave":
        pools = [(n, 1.0, 2.0) for n in ROCKS]
    elif "stream" in str(theme).lower() or "water" in str(theme).lower():
        pools = [(n, 0.9, 1.4) for n in STREAM + BUSHES]
        pools += [("tree_oak.glb", 1.6, 2.2)]
    elif theme == "stone":
        pools = [(n, 1.0, 1.8) for n in ROCKS]
        pools += [("tree_default.glb", 1.6, 2.2), ("plant_bushDetailed.glb", 0.9, 1.5)]
    else:
        pools = [(n, 1.6, 2.5) for n in TREES]
        pools += [(n, 0.9, 1.5) for n in BUSHES]

    # add a little stream life for forest too
    if theme != "cave":
        pools += [(n, 0.8, 1.5) for n in STREAM]

    loaded = []
    target = min(48, 18 + w * h // 14)
    max_attempts = target * 12
    loader = application.base.loader
    for _ in range(max_attempts):
        if len(loaded) >= target:
            break
        x = rnd.uniform(out_x0, out_x1)
        z = rnd.uniform(out_z0, out_z1)
        # must be outside maze rectangle
        if inner_x0 - 2.5 <= x <= inner_x1 + 2.5 and inner_z0 - 2.5 <= z <= inner_z1 + 2.5:
            continue
        if near_start_exit(x, z):
            continue
        file_name, s0, s1 = rnd.choice(pools)
        path = ASSETS / file_name
        if not path.exists():
            continue
        try:
            np = loader.loadModel(Filename.fromOsSpecific(str(path)))
        except Exception:
            continue
        np.reparentTo(root)
        np.setShader(application.base.render.getShader(), 10)
        np.setPos(x, 0, z)
        np.setH(rnd.uniform(0, 360))
        s = rnd.uniform(s0, s1)
        np.setScale(s, s, s)
        loaded.append(np)
    return loaded
