"""Regression for RGB images accidentally reinterpreted as RGBA in PBR."""
import pytest
from panda3d.core import Texture as PandaTexture
from lumi_maze.textures import texture_for, ground_texture

@pytest.mark.parametrize('theme,surface', [(t,s) for t in ('stone','forest','cave','streams') for s in ('floor','wall')])
def test_albedo_format_preserves_ram_layout(theme,surface):
    texture=texture_for(theme,surface)._texture
    assert texture.getNumComponents() in (3,4)
    assert texture.getFormat() == (PandaTexture.F_srgb_alpha if texture.getNumComponents()==4 else PandaTexture.F_srgb)
    assert texture.getRamImageSize() == texture.getExpectedRamImageSize()

def test_grass_format_preserves_ram_layout():
    texture=ground_texture()._texture
    assert texture.getRamImageSize() == texture.getExpectedRamImageSize()
    assert texture.getFormat() in (PandaTexture.F_srgb,PandaTexture.F_srgb_alpha)
