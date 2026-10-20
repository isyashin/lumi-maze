"""Coordinator acceptance for LUM044-047; actual engine, no gameplay monkeypatches."""
import json,math,shutil,time as clock
from pathlib import Path
from ursina import Ursina,Entity,Vec3,camera,held_keys,application,window
from panda3d.core import GeomVertexReader
from lumi_maze.main import Game
from lumi_maze.ui import GameUI
from lumi_maze.world import CELL_SIZE
app=Ursina(size=(1280,720),development_mode=False,vsync=False)
window.exit_button.visible=False;window.fps_counter.enabled=False
ui=GameUI();game=Game(app,ui);game.start_new_campaign('easy',seed=42)
out=Path('.tmp/feedback-qa');out.mkdir(parents=True,exist_ok=True)
def positions(mesh):
    reader=GeomVertexReader(mesh.geomNode.getGeom(0).getVertexData(),'vertex');p=[]
    while not reader.isAtEnd(): p.append(tuple(reader.getData3f()))
    return p
world=game.world_view
initial=(positions(world.walls.body),positions(world.walls.trim))
for i in range(5): world.update_visibility(Vec3(0,2,-4),Vec3(0,0,0),.1)
assert any(s['p']<.5 for s in world.walls.segments)
assert initial==(positions(world.walls.body),positions(world.walls.trim)), 'wall geometry moved'
assert world._scenery_bounds, 'No scenery registered'
node,bmin,bmax=world._scenery_bounds[0];original=world._scenery_orig_states[0][1]
transform=node.getMat(); center=(bmin+bmax)*.5
world.update_visibility(center,Vec3(0,0,0),.1)
assert node.getColorScale()[3]<.3, 'scenery did not fade'
world.update_visibility(Vec3(-1000,1000,-1000),Vec3(-1000,1000,-999),.1)
assert node.getState()==original and node.getMat()==transform, 'scenery not restored exactly'
print('VISIBILITY_OK unchanged wall vertices, scenery alpha and exact restore',flush=True)
trampoline=next(c for c,k in game.maze.items.items() if k=='trampoline')
previous=next(c for c in game.maze.neighbors(trampoline) if c!=game.maze.exit)
direction=(trampoline[0]-previous[0],trampoline[1]-previous[1])
return_dir=(-direction[0],-direction[1])
class Review(Entity):
    def __init__(self):
        super().__init__();self.started=clock.perf_counter();self.stage='wait';self.samples=[];self.frames=[];self.last_capture=-1;self.pause_start=None;self.takeoff=None
        self.joints=[game.fox.actor.exposeJoint(None,'modelRoot',name) for name in ('Fox_F_LLeg2','Fox_Tail3','Fox_Head')]
    def snap(self,label):
        app.graphicsEngine.render_frame();app.screenshot(namePrefix='feedback-capture.png',defaultFilename=False);target=out/(label+'.png');shutil.move('feedback-capture.png',str(target));return target
    def update(self):
        now=clock.perf_counter()
        if now-self.started>20: raise RuntimeError('Jump review timeout')
        if self.stage=='wait' and now-self.started>.8:
            self.snap('camera-start')
            game.run_state.cell=previous;game.fox.position=Vec3(previous[0]*CELL_SIZE,0,previous[1]*CELL_SIZE)
            game.cam_target.position=game.fox.position+Vec3(0,.7,0);game.cam_target_pos=Vec3(game.cam_target.position);game._reset_camera()
            assert game._try_start_move(direction)
            self.stage='approach';return
        if self.stage=='approach':
            if not game.fox._jumping:return
            self.takeoff=now;self.stage='jump'
        if self.stage=='jump':
            fox=game.fox;actor=fox.actor;actor.update(force=True)
            assert game.run_state.cell==trampoline
            if fox._jumping or game.cam_overview_active or game.overview_pending>0: assert not game._try_start_move(return_dir), 'movement allowed during bounce'
            mats=[]
            for joint in self.joints:
                m=joint.getMat(actor);mats.append(tuple(round(m.getCell(i,j),4) for i in range(4) for j in range(4)))
            self.samples.append({'t':fox._jump_timer,'y':actor.getY(),'clip':actor.getCurrentAnim(),'frame':actor.getCurrentFrame(),'inair_frame':actor.getAnimControl('InAir').getFrame(),'joints':mats,'paused':game.paused,'overview':game.cam_overview_active})
            if self.pause_start is None and .3<fox._jump_timer<.8:
                game.paused=True;self.pause_start=now;self.pause_value=(fox._jump_timer,actor.getY(),game.overview_pending,game.cam_overview_timer)
            elif game.paused and now-self.pause_start>=.25:
                assert self.pause_value==(fox._jump_timer,actor.getY(),game.overview_pending,game.cam_overview_timer), 'pause advanced flight'
                game.paused=False
            if now-self.last_capture>.10:
                self.last_capture=now;self.frames.append(self.snap('flight-'+str(len(self.frames)).zfill(2)))
            if not fox._jumping and not game.cam_overview_active and game.overview_pending<=0 and now-self.takeoff>2:
                heights=[s['y'] for s in self.samples if not s['paused']]
                assert max(heights)>3.0 and abs(heights[-1])<1e-6
                assert sum(1 for a,b in zip(heights,heights[1:]) if 0<b<a-.01)>=3, 'missing descent'
                (out/'samples.json').write_text(json.dumps(self.samples),encoding='utf8')
                airborne=[s for s in self.samples if 1.25<=s['t']<3.75 and s['y']>1]
                assert len({s['inair_frame'] for s in airborne})>=4,'frozen in-air frames'
                assert len({str(s['joints']) for s in airborne})>=4,'frozen skeletal pose'
                assert game._try_start_move(return_dir), 'movement not restored'
                (out/'samples.json').write_text(json.dumps(self.samples),encoding='utf8')
                from PIL import Image
                imgs=[Image.open(p).convert('RGB').resize((768,432)) for p in self.frames]
                imgs[0].save(out/'trampoline.gif',save_all=True,append_images=imgs[1:],duration=110,loop=0)
                print('JUMP_OK '+json.dumps({'peak':round(max(heights),2),'flight_frames':len(self.frames),'inair_pose_count':len({str(s['joints']) for s in airborne}),'pause_frozen':True,'movement_restored':True}),flush=True)
                application.quit();self.stage='done'
review=Review();app.run()



