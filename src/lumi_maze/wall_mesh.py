"""Batched wall geometry and the camera cutaway.

Every maze wall is baked into two shared Ursina meshes instead of spawning a
body/cap/plinth Entity for each segment:

* a textured body batch (hard normals, baked UVs, per-vertex tint), and
* an untextured trim batch holding the cap and plinth cubes.

A wall may later be collapsed in Y for the camera without rebuilding the mesh.
The original vertex ranges are kept and edited in place with
``GeomVertexRewriter``, which is cheap enough for the handful of walls that can
occlude the fox at once.  Collision and the maze data are never touched.
"""

from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

from panda3d.core import GeomVertexRewriter
from ursina import Entity, Mesh, application, color

FLOOR_Y = -0.12
CUT_HEIGHT = 0.18          # collapsed body height above the floor baseline
CUT_CAP_HEIGHT = 0.04      # compressed cap height at full cutaway
CUTAWAY_TIME = 0.15        # seconds to fully lower/restore one wall
OCCLUSION_RADIUS = 4.0     # only walls this close to the fox react
FOOT_OFFSET_Y = 0.30       # camera targets the fox feet, not its head
CAP_HEIGHT = 0.10

RGB = Tuple[int, int, int]
Vec3f = Tuple[float, float, float]

# Outward normal + four corners, counter-clockwise when seen from outside.
# Keeping all 24 vertices separate gives hard normals and stable UV seams.
_FACES = (
    ((1, 0, 0), ((1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1))),
    ((-1, 0, 0), ((-1, -1, -1), (-1, -1, 1), (-1, 1, 1), (-1, 1, -1))),
    ((0, 1, 0), ((-1, 1, -1), (-1, 1, 1), (1, 1, 1), (1, 1, -1))),
    ((0, -1, 0), ((-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1))),
    ((0, 0, 1), ((-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1))),
    ((0, 0, -1), ((-1, -1, -1), (-1, 1, -1), (1, 1, -1), (1, -1, -1))),
)
_FACE_UVS = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))


def _rgba(rgb: RGB) -> Tuple[float, float, float, float]:
    return (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0, 1.0)


def _append_cube(vertices: List[Vec3f], normals: List[Vec3f],
                 uvs: List[Tuple[float, float]],
                 colors: List[Tuple[float, float, float, float]],
                 triangles: List[Tuple[int, int, int]],
                 center: Vec3f, size: Vec3f, rgb: RGB,
                 uv_scale: Tuple[float, float] = (1.0, 1.0)) -> int:
    """Append one 24-vertex cube and return the first vertex row."""
    cx, cy, cz = center
    hx, hy, hz = size[0] / 2.0, size[1] / 2.0, size[2] / 2.0
    base = len(vertices)
    rgba = _rgba(rgb)

    for normal, corners in _FACES:
        face_start = len(vertices)
        for (sx, sy, sz), (u, v) in zip(corners, _FACE_UVS):
            vertices.append((cx + sx * hx, cy + sy * hy, cz + sz * hz))
            normals.append(normal)
            uvs.append((u * uv_scale[0], v * uv_scale[1]))
            colors.append(rgba)
        triangles.append((face_start, face_start + 1, face_start + 2))
        triangles.append((face_start, face_start + 2, face_start + 3))

    return base


def _as_xyz(value) -> Vec3f:
    """Accept an Ursina Vec3 or any three-item sequence."""
    try:
        return (float(value.x), float(value.y), float(value.z))
    except AttributeError:
        return (float(value[0]), float(value[1]), float(value[2]))


def _distance_to_aabb_2d(x: float, z: float,
                         bounds: Tuple[float, float, float, float]) -> float:
    min_x, max_x, min_z, max_z = bounds
    dx = min_x - x if x < min_x else (x - max_x if x > max_x else 0.0)
    dz = min_z - z if z < min_z else (z - max_z if z > max_z else 0.0)
    return math.hypot(dx, dz)


def _ray_hits_aabb(origin: Vec3f, target: Vec3f,
                   bmin: Vec3f, bmax: Vec3f) -> bool:
    """Standard slab test for the camera -> fox-foot segment."""
    t_min, t_max = 0.0, 1.0
    for axis in range(3):
        o = origin[axis]
        d = target[axis] - o
        lo, hi = bmin[axis], bmax[axis]
        if abs(d) < 1e-9:
            if o < lo or o > hi:
                return False
            continue
        t1 = (lo - o) / d
        t2 = (hi - o) / d
        if t1 > t2:
            t1, t2 = t2, t1
        if t1 > t_min:
            t_min = t1
        if t2 < t_max:
            t_max = t2
        if t_min > t_max:
            return False
    return True


def _geom_node(mesh) -> Optional[object]:
    """Return the Panda GeomNode behind a Ursina Mesh."""
    node = getattr(mesh, 'geomNode', None)
    if node is not None:
        return node
    try:
        candidate = mesh.model.node()
        if hasattr(candidate, 'modifyGeom'):
            return candidate
    except Exception:
        pass
    try:
        for match in mesh.model.findAllMatches('**/+GeomNode'):
            return match.node()
    except Exception:
        pass
    return None


class WallBatch:
    """Two shared meshes for every wall on one level, plus cutaway state."""

    def __init__(self, parent, wall_texture, floor_y: float = FLOOR_Y):
        self.parent = parent
        self.wall_texture = wall_texture
        self.floor_y = floor_y

        self._body_vertices: List[Vec3f] = []
        self._body_normals: List[Vec3f] = []
        self._body_uvs: List[Tuple[float, float]] = []
        self._body_colors: List[Tuple[float, float, float, float]] = []
        self._body_triangles: List[Tuple[int, int, int]] = []

        self._trim_vertices: List[Vec3f] = []
        self._trim_normals: List[Vec3f] = []
        self._trim_uvs: List[Tuple[float, float]] = []
        self._trim_colors: List[Tuple[float, float, float, float]] = []
        self._trim_triangles: List[Tuple[int, int, int]] = []

        self.segments: List[dict] = []
        self.body: Optional[Mesh] = None
        self.trim: Optional[Mesh] = None
        self._body_vdata = None
        self._trim_vdata = None
        self._built = False

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #
    def add_wall(self, pos: Vec3f, scale: Vec3f,
                 body_rgb: RGB, cap_rgb: RGB, plinth_rgb: RGB,
                 uv_scale: Tuple[float, float] = (1.0, 0.8)) -> None:
        """Bake one wall segment into the shared body/trim buffers."""
        x, _y, z = pos
        sx, sy, sz = scale

        body_start = _append_cube(
            self._body_vertices, self._body_normals, self._body_uvs,
            self._body_colors, self._body_triangles,
            (x, self.floor_y + sy / 2.0, z), (sx, sy, sz),
            body_rgb, uv_scale,
        )
        body_orig = list(self._body_vertices[body_start:body_start + 24])

        # Cap and plinth keep their distinct shapes and per-segment tint.
        cap_start = _append_cube(
            self._trim_vertices, self._trim_normals, self._trim_uvs,
            self._trim_colors, self._trim_triangles,
            (x, self.floor_y + sy + CAP_HEIGHT / 2.0, z),
            (sx + 0.08, CAP_HEIGHT, sz + 0.08), cap_rgb,
        )
        cap_orig = list(self._trim_vertices[cap_start:cap_start + 24])

        plinth_start = _append_cube(
            self._trim_vertices, self._trim_normals, self._trim_uvs,
            self._trim_colors, self._trim_triangles,
            (x, self.floor_y + 0.09, z),
            (sx + 0.05, 0.18, sz + 0.05), plinth_rgb,
        )

        half_x = (sx + 0.08) / 2.0 + 0.01
        half_z = (sz + 0.08) / 2.0 + 0.01
        top = self.floor_y + sy + CAP_HEIGHT + 0.01

        self.segments.append({
            'body_start': body_start,
            'body_orig': body_orig,
            'cap_start': cap_start,
            'cap_orig': cap_orig,
            'plinth_start': plinth_start,
            'sx': sx,
            'sy': sy,
            'sz': sz,
            'x': x,
            'z': z,
            'bounds_2d': (x - half_x, x + half_x, z - half_z, z + half_z),
            'bmin': (x - half_x, self.floor_y - 0.01, z - half_z),
            'bmax': (x + half_x, top, z + half_z),
            'p': 0.0,
            'target': 0.0,
        })

    def build(self) -> None:
        """Create the two Mesh entities and cache their writable vertex data."""
        if self._built or not self._body_vertices:
            return

        shader = application.base.render.getShader()
        body_mesh = Mesh(
            vertices=self._body_vertices,
            triangles=self._body_triangles,
            normals=self._body_normals,
            uvs=self._body_uvs,
            colors=self._body_colors,
            static=False,
        )
        body_entity = Entity(
            parent=self.parent,
            model=body_mesh,
            texture=self.wall_texture,
            color=color.white,
        )
        body_entity.setShader(shader, 10)
        # Keep the rendered Mesh so GeomVertexRewriter edits the visible data.
        self.body = body_entity.model
        self._body_entity = body_entity

        trim_mesh = Mesh(
            vertices=self._trim_vertices,
            triangles=self._trim_triangles,
            normals=self._trim_normals,
            uvs=self._trim_uvs,
            colors=self._trim_colors,
            static=False,
        )
        trim_entity = Entity(
            parent=self.parent,
            model=trim_mesh,
            color=color.white,
        )
        trim_entity.setShader(shader, 10)
        self.trim = trim_entity.model
        self._trim_entity = trim_entity

        self._body_vdata = self._writable_vdata(self.body)
        self._trim_vdata = self._writable_vdata(self.trim)
        self._built = True

    @staticmethod
    def _writable_vdata(mesh: Mesh):
        node = _geom_node(mesh)
        if node is None:
            return None
        try:
            return node.modifyGeom(0).modifyVertexData()
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    # Camera cutaway
    # ------------------------------------------------------------------ #
    def update_visibility(self, camera_pos, fox_pos, dt: float) -> None:
        """Collapse walls between the camera and the fox, then restore them."""
        if not self._built or self._body_vdata is None:
            return

        cam = _as_xyz(camera_pos)
        fox = _as_xyz(fox_pos)
        target = (fox[0], fox[1] + FOOT_OFFSET_Y, fox[2])
        step = max(0.0, min(float(dt), 0.1)) / CUTAWAY_TIME

        for seg in self.segments:
            near = (_distance_to_aabb_2d(fox[0], fox[2], seg['bounds_2d'])
                    <= OCCLUSION_RADIUS)
            occluding = near and _ray_hits_aabb(cam, target,
                                                seg['bmin'], seg['bmax'])
            desired = 1.0 if occluding else 0.0
            old = seg['p']

            if desired > old:
                new_p = min(1.0, old + step)
            elif desired < old:
                new_p = max(0.0, old - step)
            else:
                new_p = old

            if abs(new_p - old) < 1e-5:
                continue

            seg['p'] = new_p
            self._rewrite_segment(seg, new_p)

    def _rewrite_segment(self, seg: dict, p: float) -> None:
        """Edit only this wall's existing vertex rows in both shared meshes."""
        sy = seg['sy']
        body_h = sy + (CUT_HEIGHT - sy) * p
        body_top = self.floor_y + body_h
        cap_top = body_top + CAP_HEIGHT + (CUT_CAP_HEIGHT - CAP_HEIGHT) * p

        writer = GeomVertexRewriter(self._body_vdata, 'vertex')
        writer.setRow(seg['body_start'])
        for x, y, z in seg['body_orig']:
            t = (y - self.floor_y) / sy if sy > 1e-6 else 0.0
            writer.setData3f(x, self.floor_y + body_h * t, z)

        cap_bottom_orig = self.floor_y + sy
        writer = GeomVertexRewriter(self._trim_vdata, 'vertex')
        writer.setRow(seg['cap_start'])
        for x, y, z in seg['cap_orig']:
            t = ((y - cap_bottom_orig) / CAP_HEIGHT
                 if CAP_HEIGHT > 1e-6 else 0.0)
            t = max(0.0, min(1.0, t))
            writer.setData3f(x, body_top + (cap_top - body_top) * t, z)

        # Bounds only need to be refreshed for the two affected batches.
        for mesh in (self.body, self.trim):
            node = _geom_node(mesh)
            if node is None:
                continue
            try:
                node.markBoundsStale()
            except Exception:
                pass
