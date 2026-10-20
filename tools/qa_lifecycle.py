"""Coordinator regression: repeated level reloads must release actors and preserve shared planes."""
from ursina import Ursina, invoke, application, window
from lumi_maze.main import Game
from lumi_maze.ui import GameUI
app=Ursina(size=(1280,720),development_mode=False,vsync=False)
window.exit_button.visible=False
ui=GameUI(); game=Game(app,ui)
game.start_new_campaign('easy',seed=42)
levels=iter([2,3,4,7,1,7,1]); old=[]; bounds=[]
def step():
    level=next(levels,None)
    if level is None:
        game.return_to_menu()
        assert all(fox.actor is None for fox in old)
        print('LIFECYCLE_OK actors='+str(len(old))+' shadow_bounds='+str(bounds),flush=True)
        application.quit(); return
    previous=game.fox
    game.current_level=level; game._load_level(level)
    old.append(previous)
    assert previous.actor is None, 'old Actor not cleaned'
    film=game.sun._light.get_lens().get_film_size()
    assert 10 < max(film) < 200, 'shared plane corrupted: '+str(film)
    bounds.append(round(max(film),2))
    invoke(step,delay=.10)
invoke(step,delay=.2)
app.run()
