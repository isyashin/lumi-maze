from pathlib import Path
from ursina import Texture

# Cache for loaded textures to avoid redundant loading
_texture_cache: dict[tuple[str, str], Texture] = {}

# Mapping from theme and surface to asset filenames.
# Assets are stored in src/lumi_maze/assets/textures
_THEME_SURFACE_TO_ASSET = {
    'stone': {
        'floor': 'dirt.png',      # sandy ground; path.png is noisy cobblestone
        'wall': 'oldstone.png',   # classic stone wall
    },
    'forest': {
        'floor': 'dirt.png',
        'wall': 'paintwall.png',
    },
    'cave': {
        'floor': 'floor.png',
        'wall': 'crystal.png',    # cool crystalline cave walls
    },
    'streams': {
        'floor': 'dirt.png',
        'wall': 'underwater.png', # flowing water-stone walls
    },
}

def _asset_path(filename: str) -> str:
    """PyInstaller preserves this package-relative location via --add-data."""
    return str(Path(__file__).resolve().parent / 'assets' / 'textures' / filename)

def texture_for(theme: str, surface: str, seed: int = 0) -> Texture:
    """Return a cached :class:`ursina.Texture` for the given theme and surface.

    Parameters
    ----------
    theme: str
        One of ``'stone'``, ``'forest'``, ``'cave'`` or ``'streams'``.
    surface: str
        ``'floor'`` or ``'wall'``.
    seed: int, optional
        Kept for backward compatibility; not used for asset textures.
    """
    if theme not in _THEME_SURFACE_TO_ASSET:
        raise ValueError(f"Invalid theme: {theme}. Must be one of {_THEME_SURFACE_TO_ASSET.keys()}")
    if surface not in {'floor', 'wall'}:
        raise ValueError(f"Invalid surface: {surface}. Must be 'floor' or 'wall'")

    cache_key = (theme, surface)
    if cache_key in _texture_cache:
        return _texture_cache[cache_key]

    filename = _THEME_SURFACE_TO_ASSET[theme][surface]
    path = _asset_path(filename)
    if not Path(path).is_file():
        raise FileNotFoundError(f"Texture asset not found: {path}")

    tex = Texture(path, filtering='bilinear')
    _texture_cache[cache_key] = tex
    return tex


def ground_texture() -> Texture:
    """Painted CC0 grass used for the garden carpet around the maze."""
    cache_key = ('ground', 'grass')
    if cache_key in _texture_cache:
        return _texture_cache[cache_key]

    path = _asset_path('grasswithleafs.png')
    if not Path(path).is_file():
        raise FileNotFoundError(f"Texture asset not found: {path}")

    tex = Texture(path, filtering='bilinear')
    _texture_cache[cache_key] = tex
    return tex
