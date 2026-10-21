"""Independent deterministic camera/shadow regression; --diagnose alters QA only."""
import argparse, json, math, shutil
from pathlib import Path
from panda3d.core import ClockObject, ShaderAttrib
from ursina import Ursina, Entity, Vec3, camera, application, window
from lumi_maze.main import Game
from lumi_maze.ui import GameUI
from lumi_maze.world import CELL_SIZE

p = argparse.ArgumentParser()
p.add_argument('--out', required=True)
p.add_argument('--diagnose', choices=['normal', 'shadow-priority', 'no-shadows'], default='normal')
p.add_argument('--assert-stable', action='store_true')
p.add_argument('--level', type=int, default=1)
args = p.parse_args()
out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
app = Ursina(size=(1280, 720), development_mode=False, vsync=False)
window.exit_button.visible = False; window.fps_counter.enabled = False
clock = ClockObject.getGlobalClock(); clock.setMode(ClockObject.MNonRealTime); clock.setDt(1/60)
game = Game(app, GameUI()); game.start_new_campaign('easy', seed=42)
if args.level != 1:
    game.current_level=args.level;game._load_level(args.level)
if args.diagnose == 'no-shadows': game.sun.shadows = False
trampoline = next(c for c, k in game.maze.items.items() if k == 'trampoline')
previous = next(c for c in game.maze.neighbors(trampoline) if c != game.maze.exit)
direction = (trampoline[0]-previous[0], trampoline[1]-previous[1])

class Review(Entity):
    def __init__(self):
        super().__init__(); self.frame=0; self.samples=[]; self.images=[]; self.previous_q=None;self.walks=0
    def update(self):
        self.frame += 1
        if self.frame == 30:
            game.run_state.cell=previous
            game.fox.position=Vec3(previous[0]*CELL_SIZE,0,previous[1]*CELL_SIZE)
            game.cam_target.position=game.fox.position+Vec3(0,.7,0)
            game.cam_target_pos=Vec3(game.cam_target.position); game._reset_camera()
            assert game._try_start_move(direction)
        if self.frame == 25 and args.diagnose == 'shadow-priority':
            caster=game.sun._light; state=caster.get_initial_state()
            caster.set_initial_state(state.add_attrib(state.get_attrib(ShaderAttrib),100))
        if self.frame < 30: return
        q=camera.getQuat(app.render); delta=0
        if self.previous_q is not None:
            dot=abs(sum(q[i]*self.previous_q[i] for i in range(4)))/math.sqrt(sum(v*v for v in q)*sum(v*v for v in self.previous_q))
            delta=math.degrees(2*math.acos(min(1,dot)))
        self.previous_q=q
        self.samples.append(dict(frame=self.frame, y=game.fox.actor.getY(), jump=game.fox._jump_timer,
            phase=game.cam_overview_phase, overview=game.cam_overview_active,
            position=list(camera.world_position), rotation=list(camera.world_rotation), angle=delta))
        if self.frame>=390 and not game.move_active and self.walks<6:
            next_cell=previous if game.run_state.cell==trampoline else trampoline
            current=game.run_state.cell
            assert game._try_start_move((next_cell[0]-current[0],next_cell[1]-current[1]))
            self.walks+=1
        if self.frame%5==0:
            # Capture after the regular render; do not render an extra shadow pass.
            app.screenshot(namePrefix='stability.png',defaultFilename=False)
            target=out/f'{self.frame:04}.png';shutil.move('stability.png',target);self.images.append(target)
        if self.frame == 550:
            (out/'samples.json').write_text(json.dumps(self.samples),encoding='utf8')
            from PIL import Image
            images=[Image.open(i).convert('RGB').resize((640,360)) for i in self.images]
            images[0].save(out/'flight.gif',save_all=True,append_images=images[1:],duration=83,loop=0)
            # Motion is blocked during flight. Compare settled overhead frames,
            # apart from the animated fox/HUD, for visually unstable geometry.
            overhead=[s for s in self.samples if s['overview'] and s['phase']==1]
            print('STABILITY '+json.dumps(dict(max_angle=max(s['angle'] for s in self.samples),
                max_overhead_angle=max(s['angle'] for s in overhead[2:]),walks=self.walks,
                shadow_priority=game.sun._light.get_initial_state().get_override(ShaderAttrib.get_class_slot()),
                near=camera.lens.get_near(),far=camera.lens.get_far())),flush=True)
            if args.assert_stable:
                assert max(s['angle'] for s in self.samples)<12, 'camera orientation discontinuity'
                assert max(s['angle'] for s in overhead[2:])<.1, 'overhead camera jitters'
            application.quit()
Review();app.run()
