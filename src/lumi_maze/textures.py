from PIL import Image, ImageDraw, ImageFilter
import random
from ursina import Texture

def texture_for(theme: str, surface: str, seed: int = 0) -> Texture:
    """
    Generate a procedurally created texture for the given theme and surface.
    
    Args:
        theme: One of 'stone', 'forest', 'cave', 'streams'.
        surface: One of 'floor', 'wall'.
        seed: Random seed for reproducibility.
    
    Returns:
        ursina.Texture: A generated texture.
    """
    # Validate input
    valid_themes = {'stone', 'forest', 'cave', 'streams'}
    valid_surfaces = {'floor', 'wall'}
    if theme not in valid_themes:
        raise ValueError(f"Invalid theme: {theme}. Must be one of {valid_themes}")
    if surface not in valid_surfaces:
        raise ValueError(f"Invalid surface: {surface}. Must be one of {valid_surfaces}")

    # Initialize random with seed
    rng = random.Random(seed)
    
    # Create a blank image
    size = 128
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Define colors for each theme
    theme_colors = {
        'stone': ((128, 128, 128), (180, 180, 180), (200, 200, 200), (150, 150, 150)),
        'forest': ((50, 100, 50), (100, 150, 100), (70, 120, 70), (30, 80, 30)),
        'cave': ((30, 30, 50), (80, 80, 120), (100, 100, 150), (50, 50, 80)),
        'streams': ((100, 180, 200), (150, 220, 240), (200, 250, 250), (120, 200, 220)),
    }
    
    # Fill the background with theme color
    bg_color = theme_colors[theme][0]
    for x in range(size):
        for y in range(size):
            image.putpixel((x, y), (*bg_color, 255))
    
    # Draw theme-specific patterns
    def draw_stone_pattern():
        # Draw irregular block joints and cracks
        for _ in range(20):
            x1, y1 = rng.randint(0, size), rng.randint(0, size)
            x2, y2 = rng.randint(0, size), rng.randint(0, size)
            draw.line((x1, y1, x2, y2), fill=rng.choice(theme_colors[theme][1:]), width=rng.randint(1, 3))
        
        # Draw stone blocks
        for x in range(0, size, 20):
            for y in range(0, size, 20):
                draw.rectangle((x, y, x + 15, y + 15), fill=rng.choice(theme_colors[theme][2:]), outline=None)
    
    def draw_forest_pattern():
        # Draw leaf motifs
        for _ in range(20):
            x, y = rng.randint(0, size), rng.randint(0, size)
            draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill=rng.choice(theme_colors[theme][1:]), outline=None)
        
        # Draw tree trunks
        for _ in range(10):
            x = rng.randint(0, size)
            y = rng.randint(0, size)
            draw.rectangle((x - 2, y, x + 2, y + 20), fill=rng.choice(theme_colors[theme][2:]), outline=None)
    
    def draw_cave_pattern():
        # Draw crystal facets
        for _ in range(30):
            x, y = rng.randint(0, size), rng.randint(0, size)
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=rng.choice(theme_colors[theme][1:]), outline=None)
        
        # Draw dark rock
        for x in range(0, size, 15):
            for y in range(0, size, 15):
                draw.rectangle((x, y, x + 10, y + 10), fill=rng.choice(theme_colors[theme][2:]), outline=None)
    
    def draw_streams_pattern():
        # Draw water ripples
        for _ in range(35):
            x, y = rng.randint(0, size), rng.randint(0, size)
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=rng.choice(theme_colors[theme][1:]), outline=None)
        
        # Draw pebbles
        for _ in range(20):
            x, y = rng.randint(0, size), rng.randint(0, size)
            draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=rng.choice(theme_colors[theme][2:]), outline=None)
    
    # Apply theme-specific patterns
    if theme == 'stone':
        draw_stone_pattern()
    elif theme == 'forest':
        draw_forest_pattern()
    elif theme == 'cave':
        draw_cave_pattern()
    elif theme == 'streams':
        draw_streams_pattern()
    
    # Apply surface-specific patterns
    if surface == 'wall':
        # Add vertical lines and irregularities for walls
        for x in range(0, size, 10):
            for y in range(size):
                if rng.random() > 0.7:
                    image.putpixel((x, y), (*rng.choice(theme_colors[theme][1:]), 255))
        
        # Add vertical cracks
        for x in range(0, size, 15):
            draw.line((x, 0, x, size), fill=rng.choice(theme_colors[theme][1:]), width=rng.randint(1, 2))
    
    elif surface == 'floor':
        # Add horizontal lines and patterns for floors
        for y in range(0, size, 10):
            for x in range(size):
                if rng.random() > 0.7:
                    image.putpixel((x, y), (*rng.choice(theme_colors[theme][1:]), 255))
        
        # Add horizontal cracks
        for y in range(0, size, 15):
            draw.line((0, y, size, y), fill=rng.choice(theme_colors[theme][1:]), width=rng.randint(1, 2))
    
    # Apply slight blur for smoother texture
    image = image.filter(ImageFilter.GaussianBlur(radius=0.5))
    
    # Crop to 64x64 and return as Ursina Texture
    texture_image = image.crop((0, 0, 64, 64))
    return Texture(texture_image, filtering='bilinear')