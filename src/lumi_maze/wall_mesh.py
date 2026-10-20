"""Batched wall geometry and camera visibility handling.

Every maze wall is baked into two shared Ursina meshes instead of spawning a
body/cap/plinth Entity for each segment:

* a textured body batch (hard normals, baked UVs, per-vertex tint), and
* an untextured trim batch holding the cap and plinth cubes.

Walls that occlude the fox become semi-transparent (alpha-to-coverage MMultisample)
and return to opaque when the sightline clears. No vertex positions are modified.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from panda3d.core import GeomVertexRewriter, TransparencyAttrib
from ursina import Entity, Mesh, application, color

FLOOR_Y = -0.12
CAP_HEIGHT = 0.10
OCCLUSION_RADIUS = 12.0     # walls within this distance of fox may turn transparent
FOOT_OFFSET_Y = 0.30        # camera targets the fox feet
CHEST_OFFSET_Y = 0.95       # camera targets the fox chest (approx)
BOUNDS_EXPANSION = 0.30     # expand AABB by this much for readability
OCCLUDED_ALPHA = 0.25       # semi-transparent alpha when occluding (0.22-0.28)
TRANSPARENCY_PRIORITY = 20  # render state priority for transparency

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
                 uv_scale: Tuple[float, float] = (1.0, 1.0)) -> Tuple[int, List[Tuple[float, float, float, float]]]:
    """Append one 96-vertex rounded cube and return the first vertex row and original colors."""
    cx, cy, cz = center
    hx, hy, hz = size[0] / 2.0, size[1] / 2.0, size[2] / 2.0
    base = len(vertices)
    rgba = _rgba(rgb)
    orig_colors = []

    # Rounding radius: min(0.065, min(size) * 0.22)
    b = min(0.065, min(size) * 0.22)
    # Inner box half-extents
    inner_x = hx - b
    inner_y = hy - b
    inner_z = hz - b

    for face_normal, corners in _FACES:
        # corners: (c0, c1, c2, c3) in CCW order from outside
        c0 = corners[0]  # (sx, sy, sz)
        c1 = corners[1]
        c3 = corners[3]

        # Edge vectors from c0 (in half-size coordinate space, i.e. signs * halfsize)
        # u runs c0->c1, v runs c0->c3
        u_vec = (c1[0] - c0[0], c1[1] - c0[1], c1[2] - c0[2])
        v_vec = (c3[0] - c0[0], c3[1] - c0[1], c3[2] - c0[2])

        # Edge lengths in world space
        edge_u_len = math.sqrt((u_vec[0]*hx)**2 + (u_vec[1]*hy)**2 + (u_vec[2]*hz)**2)
        edge_v_len = math.sqrt((v_vec[0]*hx)**2 + (v_vec[1]*hy)**2 + (v_vec[2]*hz)**2)

        # Parameter fractions for 4x4 grid
        if edge_u_len > 1e-9:
            u_fracs = (0.0, b / edge_u_len, 1.0 - b / edge_u_len, 1.0)
        else:
            u_fracs = (0.0, 0.0, 1.0, 1.0)
        if edge_v_len > 1e-9:
            v_fracs = (0.0, b / edge_v_len, 1.0 - b / edge_v_len, 1.0)
        else:
            v_fracs = (0.0, 0.0, 1.0, 1.0)

        # UV fractions match the grid (0..1)
        uv_u_fracs = u_fracs
        uv_v_fracs = v_fracs

        face_verts = []  # will hold 16 vertex indices for this face

        for vi, v_frac in enumerate(v_fracs):
            for ui, u_frac in enumerate(u_fracs):
                # Bilinear position on flat face (in half-size coordinate space)
                raw_x = c0[0] + u_frac * u_vec[0] + v_frac * v_vec[0]
                raw_y = c0[1] + u_frac * u_vec[1] + v_frac * v_vec[1]
                raw_z = c0[2] + u_frac * u_vec[2] + v_frac * v_vec[2]

                # Scale to world half-size
                raw_x *= hx
                raw_y *= hy
                raw_z *= hz

                # Clamp to inner box
                core_x = max(-inner_x, min(inner_x, raw_x))
                core_y = max(-inner_y, min(inner_y, raw_y))
                core_z = max(-inner_z, min(inner_z, raw_z))

                # Delta from core to raw
                dx = raw_x - core_x
                dy = raw_y - core_y
                dz = raw_z - core_z

                # Normal
                length = math.sqrt(dx*dx + dy*dy + dz*dz)
                if length > 1e-9:
                    nx, ny, nz = dx / length, dy / length, dz / length
                else:
                    # On flat region: use face normal
                    nx, ny, nz = face_normal

                # Rounded position
                px = cx + core_x + nx * b
                py = cy + core_y + ny * b
                pz = cz + core_z + nz * b

                vertices.append((px, py, pz))
                normals.append((nx, ny, nz))
                uv_u = uv_u_fracs[ui] * uv_scale[0]
                uv_v = uv_v_fracs[vi] * uv_scale[1]
                uvs.append((uv_u, uv_v))
                colors.append(rgba)
                orig_colors.append(rgba)
                face_verts.append(len(vertices) - 1)

        # Generate triangles for 3x3 quads with same outward winding as old _FACES
        # face_verts is 4x4 grid row-major: [v0u0, v0u1, v0u2, v0u3, v1u0, ...]
        for gy in range(3):
            for gx in range(3):
                i0 = face_verts[gy * 4 + gx]
                i1 = face_verts[gy * 4 + gx + 1]
                i2 = face_verts[(gy + 1) * 4 + gx + 1]
                i3 = face_verts[(gy + 1) * 4 + gx]
                # Two triangles per quad, CCW from outside (same as original)
                triangles.append((i0, i1, i2))
                triangles.append((i0, i2, i3))

    return base, orig_colors


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

        body_start, body_orig_colors = _append_cube(
            self._body_vertices, self._body_normals, self._body_uvs,
            self._body_colors, self._body_triangles,
            (x, self.floor_y + sy / 2.0, z), (sx, sy, sz),
            body_rgb, uv_scale,
        )

        # Cap and plinth keep their distinct shapes and per-segment tint.
        cap_start, cap_orig_colors = _append_cube(
            self._trim_vertices, self._trim_normals, self._trim_uvs,
            self._trim_colors, self._trim_triangles,
            (x, self.floor_y + sy + CAP_HEIGHT / 2.0, z),
            (sx + 0.08, CAP_HEIGHT, sz + 0.08), cap_rgb,
        )

        plinth_start, plinth_orig_colors = _append_cube(
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
            'body_orig_colors': body_orig_colors,
            'cap_start': cap_start,
            'cap_orig_colors': cap_orig_colors,
            'plinth_start': plinth_start,
            'plinth_orig_colors': plinth_orig_colors,
            'sx': sx,
            'sy': sy,
            'sz': sz,
            'x': x,
            'z': z,
            'bounds_2d': (x - half_x, x + half_x, z - half_z, z + half_z),
            'bmin': (x - half_x, self.floor_y - 0.01, z - half_z),
            'bmax': (x + half_x, top, z + half_z),
            'p': 1.0,
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
        body_entity.setTransparency(TransparencyAttrib.MMultisample, TRANSPARENCY_PRIORITY)
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
        trim_entity.setTransparency(TransparencyAttrib.MMultisample, TRANSPARENCY_PRIORITY)
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
        """Make walls between camera and fox semi-transparent, then restore."""
        if not self._built or self._body_vdata is None or self._trim_vdata is None:
            return

        cam = _as_xyz(camera_pos)
        fox = _as_xyz(fox_pos)
        foot_target = (fox[0], fox[1] + FOOT_OFFSET_Y, fox[2])
        chest_target = (fox[0], fox[1] + CHEST_OFFSET_Y, fox[2])
        step = max(0.0, min(float(dt), 0.1)) * 8.0  # fast transition, ~0.125s

        for seg in self.segments:
            # Quick 2D distance cull
            near = (_distance_to_aabb_2d(fox[0], fox[2], seg['bounds_2d'])
                    <= OCCLUSION_RADIUS)

            # Expanded bounds for readability
            bmin_exp = (seg['bmin'][0] - BOUNDS_EXPANSION,
                        seg['bmin'][1] - BOUNDS_EXPANSION,
                        seg['bmin'][2] - BOUNDS_EXPANSION)
            bmax_exp = (seg['bmax'][0] + BOUNDS_EXPANSION,
                        seg['bmax'][1] + BOUNDS_EXPANSION,
                        seg['bmax'][2] + BOUNDS_EXPANSION)

            # Two rays: foot and chest
            occluding = (near and
                         (_ray_hits_aabb(cam, foot_target, bmin_exp, bmax_exp) or
                          _ray_hits_aabb(cam, chest_target, bmin_exp, bmax_exp)))

            desired = OCCLUDED_ALPHA if occluding else 1.0
            old_alpha = seg['p']  # p now stores current alpha (1.0 or OCCLUDED_ALPHA)

            if abs(desired - old_alpha) < 1e-3:
                continue

            # Smooth transition
            if desired < old_alpha:
                new_alpha = max(desired, old_alpha - step)
            else:
                new_alpha = min(desired, old_alpha + step)

            if abs(new_alpha - old_alpha) < 1e-4:
                continue

            seg['p'] = new_alpha
            self._rewrite_segment_colors(seg, new_alpha)

    def _rewrite_segment_colors(self, seg: dict, alpha: float) -> None:
        """Edit only the color-column alpha of this wall's vertices in both meshes."""
        # Body: 24 vertices
        body_writer = GeomVertexRewriter(self._body_vdata, 'color')
        body_writer.setRow(seg['body_start'])
        for r, g, b, _ in seg['body_orig_colors']:
            body_writer.setData4f(r, g, b, alpha)

        # Cap: 24 vertices
        cap_writer = GeomVertexRewriter(self._trim_vdata, 'color')
        cap_writer.setRow(seg['cap_start'])
        for r, g, b, _ in seg['cap_orig_colors']:
            cap_writer.setData4f(r, g, b, alpha)

        # Plinth: 24 vertices
        plinth_writer = GeomVertexRewriter(self._trim_vdata, 'color')
        plinth_writer.setRow(seg['plinth_start'])
        for r, g, b, _ in seg['plinth_orig_colors']:
            plinth_writer.setData4f(r, g, b, alpha)

        # Mark bounds stale so Panda recomputes if needed
        for mesh in (self.body, self.trim):
            node = _geom_node(mesh)
            if node is not None:
                try:
                    node.markBoundsStale()
                except Exception:
                    pass
