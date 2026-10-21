"""Real framebuffer regression: ghost walls must blend even with MSAA disabled."""
import argparse, json, shutil, hashlib
from pathlib import Path
from PIL import Image, ImageChops, ImageStat
from ursina import Ursina, Entity, application, window
import lumi_maze.avatar as avatar
from lumi_maze.main import Game
from lumi_maze.ui import GameUI

p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--assert-blended',action='store_true');p.add_argument('--assert-shadows',action='store_true');p.add_argument('--scenery',action='store_true');args=p.parse_args()
out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
original=avatar.simplepbr.init
avatar.simplepbr.init=lambda **kw:original(**(kw|{'msaa_samples':0}))
app=Ursina(size=(1280,720),development_mode=False,vsync=False)
window.exit_button.visible=False;window.fps_counter.enabled=False
game=Game(app,GameUI());game.start_new_campaign('easy',seed=42)
images={};shadow_hashes={}
class Review(Entity):
    def __init__(self):super().__init__();self.frame=0
    def update(self):
        self.frame+=1
        if self.frame<60:return
        game.paused=True
        if self.frame==60:game.fox.actor.stop()
        for start,label,alpha in ((65,'opaque',1.),(85,'faded',.25),(105,'hidden',0.)):
            if self.frame==start:
                for seg in game.world_view.walls.segments:game.world_view.walls._rewrite_segment_colors(seg,alpha)
                if args.scenery:
                    for node in game.world_view._scenery_nodes:node.setColorScale(1,1,1,alpha,100)
            if self.frame==start+10:
                app.screenshot(namePrefix='ghost-probe.png',defaultFilename=False)
                target=out/f'{label}.png';shutil.move('ghost-probe.png',target)
                images[label]=Image.open(target).convert('RGB').crop((0,130,1280,650))
                shadow_buffer=game.sun._light.getShadowBuffer(app.win.getGsg())
                tex=shadow_buffer.getTexture()
                assert app.graphicsEngine.extractTextureData(tex,app.win.getGsg())
                data=bytes(tex.getRamImage());assert data
                shadow_hashes[label]=hashlib.sha256(data).hexdigest()
        if self.frame==120:
            faded_diff=ImageChops.difference(images['faded'],images['hidden'])
            opaque_diff=ImageChops.difference(images['opaque'],images['hidden'])
            # Count pixels where ghost surfaces still contribute colour.
            visible=sum(max(rgb)>12 for rgb in faded_diff.getdata())
            baseline=sum(max(rgb)>12 for rgb in opaque_diff.getdata())
            result={'ghost_pixels':visible,'opaque_pixels':baseline,
                'buffers_msaa':[w.getFbProperties().getMultisamples() for w in app.graphicsEngine.getWindows()],
                'shadow_hashes':shadow_hashes,'stable_shadows':len(set(shadow_hashes.values()))==1}
            faded_diff.save(out/'ghost-contribution.png')
            (out/'result.json').write_text(json.dumps(result),encoding='utf8')
            print('TRANSPARENCY '+json.dumps(result),flush=True)
            if args.assert_blended:assert visible>baseline*.15,'ghost walls became binary holes without MSAA'
            if args.assert_shadows:assert result['stable_shadows'],'camera fade changed world shadow depth'
            application.quit()
Review();app.run()
