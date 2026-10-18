from PIL import Image, ImageDraw, ImageFilter
import random
from ursina import Texture

def texture_for(theme: str, surface: str, seed: int = 0) -> Texture:
    """
    Generate a procedurally created texture for the given theme and surface.
    """
    valid_themes = {'stone', 'forest', 'cave', 'streams'}
    valid_surfaces = {'floor', 'wall'}
    if theme not in valid_themes:
        raise ValueError(f"Invalid theme: {theme}. Must be one of {valid_themes}")
    if surface not in valid_surfaces:
        raise ValueError(f"Invalid surface: {surface}. Must be one of {valid_surfaces}")

    rng = random.Random(seed)
    size = 64
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    theme_colors = {
        'stone': ((232, 210, 180), (215, 195, 160), (240, 220, 190), (200, 175, 145)),
        'forest': ((140, 190, 100), (160, 210, 120), (100, 150, 70), (180, 220, 140)),
        'cave': ((120, 130, 170), (140, 150, 190), (100, 110, 160), (160, 170, 210)),
        'streams': ((130, 200, 230), (160, 220, 240), (80, 160, 210), (200, 240, 255)),
    }

    bg_color = theme_colors[theme][0]
    for x in range(size):
        for y in range(size):
            image.putpixel((x, y), (*bg_color, 255))

    def draw_stone_pattern():
        # Warm sandstone blocks (lower contrast, subtle)
        for _ in range(14):
            x = rng.randint(0, size - 12)
            y = rng.randint(0, size - 12)
            w = rng.randint(10, 16)
            h = rng.randint(10, 16)
            fill = rng.choice(theme_colors[theme][2:])
            draw.rectangle((x, y, x + w, y + h), fill=fill, outline=None)
        # Subtle cracks
        for _ in range(8):
            x1, y1 = rng.randint(0, size), rng.randint(0, size)
            x2, y2 = rng.randint(0, size), rng.randint(0, size)
            draw.line((x1, y1, x2, y2), fill=theme_colors[theme][1], width=1)

    def draw_forest_pattern():
        for _ in range(18):
            x, y = rng.randint(0, size), rng.randint(0, size)
            r = rng.randint(4, 9)
            fill = rng.choice(theme_colors[theme][1:])
            draw.ellipse((x - r, y - r, x + r, y + r), fill=fill, outline=None)
        for _ in range(8):
            x = rng.randint(0, size)
            y = rng.randint(0, size)
            draw.rectangle((x - 2, y, x + 2, y + 14), fill=theme_colors[theme][2], outline=None)

    def draw_cave_pattern():
        for _ in range(18):
            x, y = rng.randint(0, size), rng.randint(0, size)
            r = rng.randint(3, 6)
            fill = rng.choice(theme_colors[theme][1:])
            draw.ellipse((x - r, y - r, x + r, y + r), fill=fill, outline=None)
        for x in range(0, size, 12):
            for y in range(0, size, 12):
                w = rng.randint(8, 11)
                h = rng.randint(8, 11)
                fill = rng.choice(theme_colors[theme][2:])
                draw.rectangle((x, y, x + w, y + h), fill=fill, outline=None)

    def draw_streams_pattern():
        for _ in range(20):
            x, y = rng.randint(0, size), rng.randint(0, size)
            r = rng.randint(3, 6)
            fill = rng.choice(theme_colors[theme][1:])
            draw.ellipse((x - r, y - r, x + r, y + r), fill=fill, outline=None)
        for _ in range(12):
            x, y = rng.randint(0, size), rng.randint(0, size)
            r = rng.randint(2, 4)
            fill = rng.choice(theme_colors[theme][2:])
            draw.ellipse((x - r, y - r, x + r, y + r), fill=fill, outline=None)

    if theme == 'stone':
        draw_stone_pattern()
    elif theme == 'forest':
        draw_forest_pattern()
    elif theme == 'cave':
        draw_cave_pattern()
    elif theme == 'streams':
        draw_streams_pattern()

    if surface == 'wall':
        for x in range(0, size, 12):
            for y in range(size):
                if rng.random() > 0.75:
                    image.putpixel((x, y), (*rng.choice(theme_colors[theme][1:]), 255))
        for x in range(0, size, 16):
            draw.line((x, 0, x, size), fill=theme_colors[theme][1], width=1)
    elif surface == 'floor':
        for y in range(0, size, 12):
            for x in range(size):
                if rng.random() > 0.75:
                    image.putpixel((x, y), (*rng.choice(theme_colors[theme][1:]), 255))
        for y in range(0, size, 16):
            draw.line((0, y, size, y), fill=theme_colors[theme][1], width=1)

    image = image.filter(ImageFilter.GaussianBlur(radius=0.5))
    return Texture(image, filtering='bilinear')
