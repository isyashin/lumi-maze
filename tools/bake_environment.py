import argparse
import math
from pathlib import Path

from panda3d.core import PNMImage, Texture, Filename
from simplepbr import EnvMap
from simplepbr._ibl_funcs_cpu import calc_vector


def normalize(v):
    length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if length == 0:
        return (0.0, 0.0, 0.0)
    inv = 1.0 / length
    return (v[0] * inv, v[1] * inv, v[2] * inv)


def mix(a, b, t):
    return (a[0] * (1 - t) + b[0] * t,
            a[1] * (1 - t) + b[1] * t,
            a[2] * (1 - t) + b[2] * t)


def clamp(v):
    return (max(0.0, min(1.0, v[0])),
            max(0.0, min(1.0, v[1])),
            max(0.0, min(1.0, v[2])))


def main():
    parser = argparse.ArgumentParser(description="Bake a 32x32 cubemap environment map.")
    parser.add_argument("output", type=Path, help="Path to the output .env file")
    args = parser.parse_args()

    tex = Texture("cartoon-daylight")
    tex.setup_cube_map(32, Texture.T_unsigned_byte, Texture.F_rgb)

    horizon_color = (0.18, 0.20, 0.23)
    sky_color = (0.22, 0.28, 0.40)
    ground_color = (0.075, 0.095, 0.055)
    warm_soft_key = (0.50, 0.42, 0.28)
    warm_dir = normalize((-0.4, 0.8, -0.4))

    size = 32
    for face in range(6):
        img = PNMImage(size, size, 3)
        for y in range(size):
            for x in range(size):
                vec = calc_vector(size, face, x, y)
                d = normalize(vec)
                dy = d[1]
                if dy >= 0:
                    base = mix(horizon_color, sky_color, dy)
                else:
                    base = mix(horizon_color, ground_color, -dy)
                # warm soft key contribution
                dot = max(
                    d[0] * warm_dir[0] + d[1] * warm_dir[1] + d[2] * warm_dir[2],
                    0.0,
                )
                warm_factor = dot ** 8
                warm = (warm_soft_key[0] * warm_factor,
                        warm_soft_key[1] * warm_factor,
                        warm_soft_key[2] * warm_factor)
                color = (base[0] + warm[0], base[1] + warm[1], base[2] + warm[2])
                r, g, b = clamp(color)
                img.setXel(x, y, r, g, b)
        assert tex.load(img, face, 0)

    tex.set_minfilter(Texture.FT_linear)
    tex.set_magfilter(Texture.FT_linear)
    # Optional wrap mode can stay at default (Clamp)

    env = EnvMap(
        tex,
        prefiltered_size=32,
        prefiltered_samples=16,
        blocking_prepare=True,
    )

    output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    env.write(Filename.fromOsSpecific(str(output_path.resolve())))

    # Verify the file exists and is non‑zero
    assert output_path.is_file() and output_path.stat().st_size > 0, "Failed to write .env file"

    # Print diagnostics
    sh_count = len(env.sh_coefficients)
    print(f"Wrote environment map to {output_path}")
    print(f"File size: {output_path.stat().st_size} bytes")
    print(f"SH coefficient count: {sh_count}")


if __name__ == "__main__":
    main()
