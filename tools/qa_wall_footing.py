"""Pixel regression for floor leakage through wall plinths; uses engine two-sided depth as oracle."""
import argparse,json,shutil
from pathlib import Path
from PIL import Image,ImageChops,ImageFilter
from ursina import Ursina,Entity,Vec3,camera,window,application,color
from ursina.shaders import unlit_shader
from panda3d.core import CullFaceAttrib
from lumi_maze.avatar import prepare_avatar_rendering
from lumi_maze.wall_mesh import WallBatch,FLOOR_Y

p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--assert-sealed',action='store_true');args=p.parse_args()
out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
app=Ursina(size=(960,720),development_mode=False,vsync=False)
window.exit_button.visible=False;window.fps_counter.enabled=False
prepare_avatar_rendering()
floor=Entity(model='plane',scale=(20,1,20),y=FLOOR_Y,color=color.rgb32(255,0,255),shader=unlit_shader)
floor.setShader(unlit_shader._shader,100)
batch=WallBatch(Entity(),None)
batch.add_wall((0,0,0),(.26,1.55,6.),(24,80,210),(170,170,170),(170,170,170))
batch.build()
meshes=(batch._body_entity,batch._trim_entity)
for mesh in meshes:mesh.setShader(unlit_shader._shader,100)
camera.parent=application.base.render;camera.fov=60;camera.clip_plane_near=.1;camera.clip_plane_far=60
# Include small camera translations on each side: these previously made the
# coincident underside/floor alternate in visible scanlines.
poses=[(x+dx,1.2,z) for x,z in ((1.8,-2.),(-1.8,-2.),(1.8,2.),(-1.8,2.)) for dx in (-.04,0.,.04)]
results=[];oracle=None

def capture(name):
    app.screenshot(namePrefix='footing-capture.png',defaultFilename=False)
    path=out/(name+'.png');shutil.move('footing-capture.png',path)
    return Image.open(path).convert('RGB')

class Review(Entity):
    def __init__(self):super().__init__();self.frame=0
    def update(self):
        global oracle
        self.frame+=1
        if self.frame<30:return
        idx=(self.frame-30)//30;t=(self.frame-30)%30
        if idx==len(poses):
            (out/'results.json').write_text(json.dumps(results),encoding='utf8')
            print('FOOTING '+json.dumps(results),flush=True)
            if args.assert_sealed:
                assert all(r['trim_pixels']>100 for r in results),'empty oracle mask'
                assert all(r['floor_leak_pixels']==0 for r in results),'floor visible inside solid plinth surface'
            application.quit();return
        if t==0:
            camera.position=Vec3(*poses[idx]);camera.rotation=(0,0,0);camera.look_at(Vec3(0,.05,0))
            # Two-sided depth chooses the physically nearest exterior regardless
            # of submitted winding; the ground stays identical in both passes.
            floor.y=FLOOR_Y
            for mesh in meshes:mesh.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullNone),100)
        if t==8:
            im=capture(f'{idx}-oracle')
            oracle=Image.new('L',im.size);oracle.putdata([255 if 60<g<230 and abs(r-g)<3 and abs(b-g)<3 else 0 for r,g,b in im.getdata()])
            oracle=oracle.filter(ImageFilter.MinFilter(3))
        if t==10:
            floor.y=FLOOR_Y
            for mesh in meshes:mesh.clearAttrib(CullFaceAttrib)
        if t==18:
            im=capture(f'{idx}-actual')
            pink=Image.new('L',im.size);pink.putdata([255 if r>120 and b>120 and g<30 else 0 for r,g,b in im.getdata()])
            leaks=ImageChops.multiply(oracle,pink)
            leaks.save(out/f'{idx}-leaks.png')
            results.append({'view':idx,'trim_pixels':sum(v>0 for v in oracle.getdata()),'floor_leak_pixels':sum(v>0 for v in leaks.getdata())})
Review();app.run()
