"""Rounded wall surfaces must stay inside collision bounds and face outward."""
import math
import pytest
from lumi_maze.wall_mesh import _append_cube
from ursina.models.procedural.cube import Cube


def native_cube_winding_sign():
    """Use Ursina's own visible cube as the handedness reference, not a guess."""
    cube=Cube()
    signs=[]
    for face in cube.triangles:
        a,b,c=[cube.vertices[i] for i in face[:3]]
        ab=b-a;ac=c-a
        centroid=(a+b+c)/3
        signed=ab.cross(ac).dot(centroid)
        assert abs(signed)>1e-6
        signs.append(1 if signed>0 else -1)
    assert len(set(signs))==1
    return signs[0]

@pytest.mark.parametrize('size',[(3.,1.55,.26),(.34,.1,3.08),(.31,.18,3.05)])
def test_rounded_wall_bounds_normals_and_winding(size):
    winding_sign=native_cube_winding_sign()
    vertices=[];normals=[];uvs=[];colors=[];triangles=[]
    first,original_colors=_append_cube(vertices,normals,uvs,colors,triangles,(0.,0.,0.),size,(220,185,130))
    assert first==0 and len(vertices)==len(normals)==len(original_colors)==96
    for axis in range(3):
        assert min(v[axis] for v in vertices)>=-size[axis]/2-1e-8
        assert max(v[axis] for v in vertices)<=size[axis]/2+1e-8
    assert all(math.isclose(sum(c*c for c in n),1.,abs_tol=1e-6) for n in normals)
    for indices in triangles:
        a,b,c=[vertices[i] for i in indices]
        ab=[b[i]-a[i] for i in range(3)];ac=[c[i]-a[i] for i in range(3)]
        cross=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
        normal_sum=[sum(normals[j][i] for j in indices) for i in range(3)]
        assert winding_sign*sum(cross[i]*normal_sum[i] for i in range(3))>1e-10, 'winding differs from native Ursina cube'
