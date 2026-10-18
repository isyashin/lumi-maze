import pytest
from lumi_maze.core import Maze, Cell
from lumi_maze.rules import RunState

# Helper to create the specific maze used in all tests
def make_maze() -> Maze:
    width, height = 3, 2
    passages = frozenset(
        {
            ((0, 0), (1, 0)),
            ((1, 0), (2, 0)),
            ((2, 0), (2, 1)),
            ((2, 1), (1, 1)),
            ((1, 1), (0, 1)),
        }
    )
    items = {
        (1, 0): "apple",
        (2, 0): "strawberry",
        (2, 1): "strawberry",
        (1, 1): "trampoline",
    }
    return Maze(
        width=width,
        height=height,
        passages=passages,
        start=(0, 0),
        exit=(0, 1),
        items=items,
        theme="test",
        time_limit=100.0,
    )

@pytest.fixture
def maze():
    return make_maze()

def test_initial_state(maze):
    rs = RunState(maze, mode="timed")
    assert rs.cell == maze.start
    assert rs.status == "playing"
    assert rs.time_left == 100.0
    assert rs.freeze_left == 0.0
    assert rs.speed_factor == 1.0
    assert rs.steps == 0
    assert rs.collected == set()

def test_illegal_move_no_change(maze):
    rs = RunState(maze, mode="timed")
    # (0,0) to (0,1) is not a direct passage
    result = rs.try_move((0, 1))
    assert result is None
    assert rs.cell == maze.start
    assert rs.steps == 0
    assert rs.status == "playing"

def test_apple_collect_and_tick(maze):
    rs = RunState(maze, mode="timed")
    assert rs.try_move((1, 0)) == "apple"
    assert rs.freeze_left == 10.0
    # advance 12 seconds: 10 frozen, 2 counted
    rs.tick(12.0)
    assert rs.freeze_left == 0.0
    # time left should have decreased by 2 seconds (speed_factor = 1)
    assert rs.time_left == pytest.approx(98.0)

def test_strawberry_speed_factor(maze):
    rs = RunState(maze, mode="timed")
    rs.try_move((1, 0))  # apple, ignore result
    rs.try_move((2, 0))  # first strawberry
    assert rs.speed_factor == pytest.approx(0.5)
    rs.try_move((2, 1))  # second strawberry
    assert rs.speed_factor == pytest.approx(0.25)

def test_revisit_fruit_no_extra_effect(maze):
    rs = RunState(maze, mode="timed")
    rs.try_move((1, 0))  # collect apple
    assert rs.freeze_left == 10.0
    rs.try_move((0, 0))  # back to start, no fruit
    # revisit apple cell – should not add freeze again
    rs.try_move((1, 0))
    assert rs.freeze_left == 10.0  # unchanged

def test_trampoline_event_before_exit(maze):
    rs = RunState(maze, mode="timed")
    # Move along optimal route up to trampoline
    rs.try_move((1, 0))
    rs.try_move((2, 0))
    rs.try_move((2, 1))
    assert rs.try_move((1, 1)) == "trampoline"
    assert rs.status == "playing"
    assert rs.cell == (1, 1)

def test_optimal_win_points_timed(maze):
    rs = RunState(maze, mode="timed")
    # follow optimal 5‑move path
    rs.try_move((1, 0))
    rs.try_move((2, 0))
    rs.try_move((2, 1))
    rs.try_move((1, 1))
    rs.try_move((0, 1))
    assert rs.status == "won"
    # timed mode gives no fruit points, route is optimal → 1000
    assert rs.level_points == 1000

def test_backtrack_points_timed(maze):
    rs = RunState(maze, mode="timed")
    # 7‑move route: apple, back, apple again, strawberry, strawberry, trampoline, exit
    rs.try_move((1, 0))  # apple
    rs.try_move((0, 0))  # back
    rs.try_move((1, 0))  # revisit apple (no extra effect)
    rs.try_move((2, 0))
    rs.try_move((2, 1))
    rs.try_move((1, 1))
    rs.try_move((0, 1))
    assert rs.status == "won"
    # optimum = 5, steps = 7 → round(1000*5/7) = 714
    assert rs.level_points == 714

def test_easy_mode_fruit_points(maze):
    rs = RunState(maze, mode="easy")
    rs.try_move((1, 0))  # apple → +150
    rs.try_move((2, 0))  # strawberry → +150
    rs.try_move((2, 1))  # strawberry → +150
    rs.try_move((1, 1))  # trampoline (no points)
    rs.try_move((0, 1))  # exit
    assert rs.status == "won"
    # route points are optimal (1000) + fruit points (450)
    assert rs.level_points == 1450
    assert rs.fruit_points == 450

def test_timeout_prevents_move_and_status_lost(maze):
    rs = RunState(maze, mode="timed")
    rs.tick(100.0)  # deplete timer
    assert rs.status == "lost"
    # any further move is ignored
    assert rs.try_move((1, 0)) is None
    assert rs.cell == maze.start

def test_negative_dt_raises(maze):
    rs = RunState(maze, mode="timed")
    with pytest.raises(ValueError):
        rs.tick(-0.1)
