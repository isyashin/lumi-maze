#!/usr/bin/env python3
"""Smooth the NORMAL attributes of an embedded-buffer glTF 2.0 file.

Only float32 VEC3 normal triplets are rewritten.  Embedded base64 buffer
data URIs are decoded locally and re-encoded; no external resource is read.

Usage:
    python tools/smooth_fox.py INPUT.gltf OUTPUT.gltf [--crease 75]
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import math
import os
import struct
import sys

FLOAT32_COMPONENT_TYPE = 5126
VEC3_TYPE = "VEC3"
FLOAT3_BYTES = 12
FLOAT3 = struct.Struct("<3f")


class SmoothError(Exception):
    """A user-facing input, format, or writing error."""


class Float3Accessor:
    """The byte layout of one float32 VEC3 accessor."""

    __slots__ = ("index", "count", "stride", "start", "buffer_index", "label")

    def __init__(self, index, count, stride, start, buffer_index, label):
        self.index = index
        self.count = count
        self.stride = stride
        self.start = start
        self.buffer_index = buffer_index
        self.label = label

    def read_values(self, data):
        return [
            FLOAT3.unpack_from(data, self.start + vertex * self.stride)
            for vertex in range(self.count)
        ]

    def write_value(self, data, vertex, normal):
        FLOAT3.pack_into(
            data,
            self.start + vertex * self.stride,
            normal[0],
            normal[1],
            normal[2],
        )


def _require(condition, message):
    if not condition:
        raise SmoothError(message)


def _as_int(value, label, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int):
        raise SmoothError("{0} must be an integer; got {1!r}".format(label, value))
    if value < minimum:
        raise SmoothError("{0} must be at least {1}; got {2}".format(label, minimum, value))
    return value


def _as_finite_float(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SmoothError("{0} must be a number; got {1!r}".format(label, value))
    number = float(value)
    if not math.isfinite(number):
        raise SmoothError("{0} must be finite; got {1!r}".format(label, value))
    return number


def _paths_are_the_same(first, second):
    try:
        if os.path.exists(first) and os.path.exists(second):
            if os.path.samefile(first, second):
                return True
    except OSError:
        pass
    first_real = os.path.normcase(os.path.realpath(os.path.abspath(first)))
    second_real = os.path.normcase(os.path.realpath(os.path.abspath(second)))
    return first_real == second_real


def _read_document(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            document = json.load(handle)
    except OSError as exc:
        raise SmoothError("cannot read input {0}: {1}".format(path, exc))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise SmoothError("invalid JSON in {0}: {1}".format(path, exc))

    _require(isinstance(document, dict), "input JSON must be a glTF object")
    asset = document.get("asset")
    _require(isinstance(asset, dict), "input has no glTF 'asset' object")
    version = asset.get("version")
    _require(
        isinstance(version, str) and version.split(".", 1)[0] == "2",
        "input is not a glTF 2.x document (asset.version={0!r})".format(version),
    )
    return document


def _decode_buffers(document):
    buffers = document.get("buffers")
    _require(
        isinstance(buffers, list) and len(buffers) > 0,
        "glTF 'buffers' must be a non-empty array",
    )

    decoded = []
    headers = []
    for index, buffer in enumerate(buffers):
        _require(isinstance(buffer, dict), "buffer {0} must be an object".format(index))
        uri = buffer.get("uri")
        _require(
            isinstance(uri, str) and len(uri) > 0,
            "buffer {0} has no embedded data URI".format(index),
        )
        _require(
            uri[:5].lower() == "data:",
            "buffer {0} uses an external URI; only embedded base64 data URIs "
            "are supported and no external resource is read".format(index),
        )

        header, separator, payload = uri.partition(",")
        _require(
            bool(separator),
            "buffer {0} has a malformed data URI (missing comma)".format(index),
        )
        header_parts = header.split(";")
        _require(
            any(part.lower() == "base64" for part in header_parts[1:]),
            "buffer {0} data URI is not base64 encoded".format(index),
        )
        try:
            raw = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise SmoothError(
                "buffer {0} contains invalid base64 data: {1}".format(index, exc)
            )

        byte_length = _as_int(
            buffer.get("byteLength"), "buffer {0}.byteLength".format(index), 0
        )
        _require(
            len(raw) >= byte_length,
            "buffer {0} decodes to {1} bytes, shorter than byteLength {2}".format(
                index, len(raw), byte_length
            ),
        )
        decoded.append(bytearray(raw))
        headers.append(header)

    return decoded, headers


def _float3_accessor(document, decoded_buffers, accessor_index, label):
    accessors = document.get("accessors")
    _require(isinstance(accessors, list), "glTF 'accessors' must be an array")

    index = _as_int(accessor_index, label + " accessor index")
    _require(
        index < len(accessors),
        "{0}: accessor {1} is out of range".format(label, index),
    )
    accessor = accessors[index]
    _require(
        isinstance(accessor, dict),
        "{0}: accessor {1} must be an object".format(label, index),
    )

    count = _as_int(
        accessor.get("count"), "{0}: accessor {1} count".format(label, index), 0
    )
    component_type = accessor.get("componentType")
    _require(
        component_type == FLOAT32_COMPONENT_TYPE,
        "{0}: accessor {1} must use componentType 5126 (float32); got {2!r}".format(
            label, index, component_type
        ),
    )
    accessor_type = accessor.get("type")
    _require(
        accessor_type == VEC3_TYPE,
        "{0}: accessor {1} must be type VEC3; got {2!r}".format(
            label, index, accessor_type
        ),
    )
    _require(
        not accessor.get("normalized", False),
        "{0}: accessor {1} is normalized, which is unsupported for float32 "
        "positions or normals".format(label, index),
    )
    _require(
        accessor.get("sparse") is None,
        "{0}: accessor {1} uses sparse storage, which is unsupported".format(
            label, index
        ),
    )

    view_index = _as_int(
        accessor.get("bufferView"),
        "{0}: accessor {1} bufferView".format(label, index),
    )
    buffer_views = document.get("bufferViews")
    _require(isinstance(buffer_views, list), "glTF 'bufferViews' must be an array")
    _require(
        view_index < len(buffer_views),
        "{0}: accessor {1} references missing bufferView {2}".format(
            label, index, view_index
        ),
    )
    view = buffer_views[view_index]
    _require(
        isinstance(view, dict),
        "{0}: bufferView {1} must be an object".format(label, view_index),
    )

    buffer_index = _as_int(
        view.get("buffer"), "{0}: bufferView {1} buffer".format(label, view_index)
    )
    buffers = document.get("buffers")
    _require(
        buffer_index < len(decoded_buffers) and buffer_index < len(buffers),
        "{0}: bufferView {1} references missing buffer {2}".format(
            label, view_index, buffer_index
        ),
    )
    byte_length = _as_int(
        buffers[buffer_index].get("byteLength"),
        "buffer {0}.byteLength".format(buffer_index),
        0,
    )
    _require(
        len(decoded_buffers[buffer_index]) >= byte_length,
        "buffer {0} decoded data is shorter than byteLength".format(buffer_index),
    )

    view_offset = _as_int(
        view.get("byteOffset", 0),
        "{0}: bufferView {1} byteOffset".format(label, view_index),
    )
    view_length = _as_int(
        view.get("byteLength"),
        "{0}: bufferView {1} byteLength".format(label, view_index),
    )
    view_end = view_offset + view_length
    _require(
        view_end <= byte_length,
        "{0}: bufferView {1} exceeds buffer {2} byteLength".format(
            label, view_index, buffer_index
        ),
    )

    accessor_offset = _as_int(
        accessor.get("byteOffset", 0),
        "{0}: accessor {1} byteOffset".format(label, index),
    )
    _require(
        accessor_offset <= view_length,
        "{0}: accessor {1} byteOffset lies outside bufferView {2}".format(
            label, index, view_index
        ),
    )

    if "byteStride" in view:
        stride = _as_int(
            view.get("byteStride"),
            "{0}: bufferView {1} byteStride".format(label, view_index),
            FLOAT3_BYTES,
        )
        _require(
            stride <= 252,
            "{0}: bufferView {1} byteStride {2} exceeds 252".format(
                label, view_index, stride
            ),
        )
        _require(
            stride % 4 == 0,
            "{0}: bufferView {1} byteStride {2} is not a multiple of 4".format(
                label, view_index, stride
            ),
        )
    else:
        stride = FLOAT3_BYTES

    start = view_offset + accessor_offset
    if count:
        accessor_end = start + (count - 1) * stride + FLOAT3_BYTES
        _require(
            accessor_end <= view_end,
            "{0}: accessor {1} with {2} vertices exceeds bufferView {3} "
            "bounds".format(label, index, count, view_index),
        )

    return Float3Accessor(index, count, stride, start, buffer_index, label)


def _read_finite_values(accessor, data, kind):
    values = accessor.read_values(data)
    for vertex, value in enumerate(values):
        if not all(math.isfinite(component) for component in value):
            raise SmoothError(
                "{0}: non-finite {1} at vertex {2}".format(
                    accessor.label, kind, vertex
                )
            )
    return values


def _smooth_primitive(positions, normals, normal_accessor, normal_data, crease_degrees):
    groups = {}
    for vertex, position in enumerate(positions):
        key = (
            round(position[0], 5),
            round(position[1], 5),
            round(position[2], 5),
        )
        groups.setdefault(key, []).append(vertex)

    threshold = math.cos(math.radians(crease_degrees))
    # normals is an immutable snapshot of the original values for this primitive.
    snapshot = normals

    for neighbors in groups.values():
        for vertex in neighbors:
            original = snapshot[vertex]
            total_x = 0.0
            total_y = 0.0
            total_z = 0.0
            for neighbor in neighbors:
                candidate = snapshot[neighbor]
                dot = (
                    original[0] * candidate[0]
                    + original[1] * candidate[1]
                    + original[2] * candidate[2]
                )
                if dot >= threshold:
                    total_x += candidate[0]
                    total_y += candidate[1]
                    total_z += candidate[2]

            length_squared = total_x * total_x + total_y * total_y + total_z * total_z
            if length_squared <= 0.0 or not math.isfinite(length_squared):
                # The original bytes are still in place, which retains the normal.
                continue
            inverse_length = 1.0 / math.sqrt(length_squared)
            normal_accessor.write_value(
                normal_data,
                vertex,
                (
                    total_x * inverse_length,
                    total_y * inverse_length,
                    total_z * inverse_length,
                ),
            )


def _smooth_document(document, decoded_buffers, crease_degrees):
    meshes = document.get("meshes", [])
    _require(isinstance(meshes, list), "glTF 'meshes' must be an array")

    processed_normal_accessors = set()
    processed_vertices = 0

    for mesh_index, mesh in enumerate(meshes):
        _require(
            isinstance(mesh, dict),
            "mesh {0} must be an object".format(mesh_index),
        )
        primitives = mesh.get("primitives")
        _require(
            isinstance(primitives, list),
            "mesh {0}: 'primitives' must be an array".format(mesh_index),
        )

        for primitive_index, primitive in enumerate(primitives):
            _require(
                isinstance(primitive, dict),
                "mesh {0} primitive {1} must be an object".format(
                    mesh_index, primitive_index
                ),
            )
            attributes = primitive.get("attributes", {})
            if attributes is None:
                continue
            _require(
                isinstance(attributes, dict),
                "mesh {0} primitive {1}: 'attributes' must be an object".format(
                    mesh_index, primitive_index
                ),
            )
            if "POSITION" not in attributes or "NORMAL" not in attributes:
                continue

            label = "mesh {0} primitive {1}".format(mesh_index, primitive_index)
            position_index = _as_int(
                attributes["POSITION"], label + " POSITION attribute"
            )
            normal_index = _as_int(attributes["NORMAL"], label + " NORMAL attribute")

            # A shared NORMAL accessor is intentionally handled only once.  It may
            # also be used by a later primitive of another mesh.
            if normal_index in processed_normal_accessors:
                continue
            _require(
                position_index != normal_index,
                "{0}: POSITION and NORMAL reference the same accessor; writing "
                "normals would change positions".format(label),
            )

            position_accessor = _float3_accessor(
                document, decoded_buffers, position_index, label + " POSITION"
            )
            normal_accessor = _float3_accessor(
                document, decoded_buffers, normal_index, label + " NORMAL"
            )
            _require(
                position_accessor.count == normal_accessor.count,
                "{0}: POSITION count {1} does not match NORMAL count {2}".format(
                    label, position_accessor.count, normal_accessor.count
                ),
            )

            positions = _read_finite_values(
                position_accessor,
                decoded_buffers[position_accessor.buffer_index],
                "position",
            )
            normals = _read_finite_values(
                normal_accessor,
                decoded_buffers[normal_accessor.buffer_index],
                "normal",
            )

            _smooth_primitive(
                positions,
                normals,
                normal_accessor,
                decoded_buffers[normal_accessor.buffer_index],
                crease_degrees,
            )
            processed_normal_accessors.add(normal_index)
            processed_vertices += normal_accessor.count

    return len(processed_normal_accessors), processed_vertices


def _reencode_buffer_uris(document, decoded_buffers, headers):
    buffers = document.get("buffers")
    _require(
        isinstance(buffers, list) and len(buffers) == len(decoded_buffers) == len(headers),
        "internal buffer count mismatch while encoding output",
    )
    for index, buffer in enumerate(buffers):
        _require(isinstance(buffer, dict), "buffer {0} must be an object".format(index))
        payload = base64.b64encode(bytes(decoded_buffers[index])).decode("ascii")
        buffer["uri"] = headers[index] + "," + payload


def _write_document(path, document):
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                document,
                handle,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
            handle.write("\n")
    except (OSError, ValueError) as exc:
        raise SmoothError("cannot write output {0}: {1}".format(path, exc))


def _run(args):
    crease_degrees = _as_finite_float(args.crease, "--crease")
    _require(
        0.0 <= crease_degrees <= 180.0,
        "--crease must be between 0 and 180 degrees; got {0:g}".format(
            crease_degrees
        ),
    )
    _require(
        not _paths_are_the_same(args.input, args.output),
        "output path must differ from input path; refusing to overwrite the input",
    )
    _require(
        os.path.isfile(args.input),
        "input file not found: {0}".format(args.input),
    )

    document = _read_document(args.input)
    decoded_buffers, headers = _decode_buffers(document)
    accessor_count, vertex_count = _smooth_document(
        document, decoded_buffers, crease_degrees
    )
    _reencode_buffer_uris(document, decoded_buffers, headers)
    _write_document(args.output, document)

    print(
        "Smoothed {0} NORMAL accessor(s), {1} vertices; crease {2:g} deg -> {3}".format(
            accessor_count, vertex_count, crease_degrees, args.output
        )
    )


def _parse_args(argv):
    parser = argparse.ArgumentParser(
        description=(
            "Smooth float32 VEC3 NORMAL data in an embedded-buffer glTF 2.0 "
            "file while preserving hard creases."
        )
    )
    parser.add_argument("input", help="input .gltf file")
    parser.add_argument("output", help="output .gltf file (must differ from input)")
    parser.add_argument(
        "--crease",
        type=float,
        default=75.0,
        metavar="DEGREES",
        help="crease angle threshold in degrees (default: 75)",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)
    try:
        _run(args)
    except SmoothError as exc:
        print("error: {0}".format(exc), file=sys.stderr)
        return 1
    except Exception as exc:  # Keep CLI failures concise and non-zero.
        print("error: {0}".format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
