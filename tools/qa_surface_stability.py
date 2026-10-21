"""Controlled subpixel camera motion: expose depth conflicts on frozen surfaces."""
import argparse, json, shutil
from pathlib import Path
from panda3d.core import ShaderAttrib, TransparencyAttrib
from ursina import Ursina, Entity, Vec3, camera, application, window
from lumi_maze.main import Game
from lumi_maze.ui import GameUI
from lumi_maze.world import CELL_SIZE
from PIL import Image, ImageChops, ImageStat

p=argparse.ArgumentParser();p.add_argument('--out',required=True);args=p.parse_args()
out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
app=Ursina(size=(1280,720),development_mode=False,vsync=False)
window.exit_button.visible=False;window.fps_counter.enabled=False
game=Game(app,GameUI());game.start_new_campaign('easy',seed=42)
cell=game.maze.shortest_path()[len(game.maze.shortest_path())//2]
game.run_state.cell=cell;game.fox.position=Vec3(cell[0]*CELL_SIZE,0,cell[1]*CELL_SIZE)
game.cam_target.position=game.fox.position+Vec3(0,.7,0)
game.cam_target_pos=Vec3(game.cam_target.position);game._reset_camera()
states=['normal','shadow','bias','opaque'];frames={};results={}

class Review(Entity):
    def __init__(self): super().__init__();self.frame=0;self.state_index=-1
    def update(self):
        self.frame+=1
        if self.frame<50:return
        if self.frame==50:game.fox.actor.stop()
        game.paused=True
        local=(self.frame-50)%30;index=(self.frame-50)//30
        if index>=len(states):
            (out/'results.json').write_text(json.dumps(results),encoding='utf8')
            print('SURFACES '+json.dumps(results),flush=True);application.quit();return
        name=states[index]
        if local==0:
            if name=='shadow':
                caster=game.sun._light;state=caster.get_initial_state()
                caster.set_initial_state(state.add_attrib(state.get_attrib(ShaderAttrib),100))
            elif name=='bias':app.render.set_shader_input('global_shadow_bias',.005)
            elif name=='opaque':
                for seg in game.world_view.walls.segments:game.world_view.walls._rewrite_segment_colors(seg,1)
                for entity in (game.world_view.walls._body_entity,game.world_view.walls._trim_entity):
                    entity.setTransparency(TransparencyAttrib.MNone,100)
            frames[name]=[]
        if local in (5,15):game.cam_target.x=game.cam_target_pos.x+(0 if local==5 else .0005)
        if local in (10,20):
            app.screenshot(namePrefix='surface.png',defaultFilename=False)
            target=out/f'{name}-{local}.png';shutil.move('surface.png',target);frames[name].append(target)
        if local==22:
            a,b=[Image.open(f).convert('RGB').crop((0,130,1280,650)) for f in frames[name]]
            diff=ImageChops.difference(a,b);diff.save(out/f'{name}-diff.png')
            values=[max(rgb) for rgb in diff.getdata()]
            results[name]={'mean_difference':sum(ImageStat.Stat(diff).mean)/3,
                          'changed_over_20':sum(v>20 for v in values),'pixels':len(values)}
Review();app.run()
